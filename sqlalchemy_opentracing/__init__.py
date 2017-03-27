from sqlalchemy.event import contains, listen, remove
from sqlalchemy.orm import Session

g_tracer = None
g_trace_all = True

def init_tracing(tracer, trace_all=False):
    '''
    Set our global tracer.
    Tracer objects from our pyramid/flask/django libraries
    can be passed as well.
    '''
    global g_tracer, g_trace_all
    if hasattr(tracer, '_tracer'):
        g_tracer = tracer._tracer
    else:
        g_tracer = tracer

    g_trace_all = trace_all

def get_traced(obj):
    '''
    Gets a bool indicating whether or not this
    object is marked for tracing.
    '''
    return getattr(obj, '_traced', False)

def set_traced(obj):
    '''
    Mark a statement/session to be traced.
    '''
    obj._traced = True

    # Session needs to have its connection/statements
    # decorated as soon as a connection is acquired.
    if isinstance(obj, Session):
        _register_session_connection_event(obj)

def get_parent_span(obj):
    '''
    Gets a parent span for this object, if any.
    '''
    return getattr(obj, '_parent_span', None)

def set_parent_span(obj, parent_span):
    '''
    Marks an object as a child of a span.
    It gets marked to be traced if it wasn't before.
    '''
    obj._parent_span = parent_span
    set_traced(obj)

def has_parent_span(obj):
    '''
    Get whether or not the statement has
    a parent span.
    '''
    return hasattr(obj, '_parent_span')

def get_span(obj):
    '''
    Get the span of a statement object, if any.
    '''
    return getattr(obj, '_span', None)

def register_connectable(obj):
    '''
    Register an object to have its events be traced.
    Any Connectable object is accepted, which
    includes Connection and Engine.
    '''
    listen(obj, 'before_cursor_execute', _connectable_before_cursor_handler)
    listen(obj, 'after_cursor_execute', _connectable_after_cursor_handler)
    listen(obj, 'handle_error', _connectable_error_handler)

def unregister_connectable(obj):
    '''
    Remove a connectable from having its events being
    traced.
    '''
    remove(obj, 'before_cursor_execute', _connectable_before_cursor_handler)
    remove(obj, 'after_cursor_execute', _connectable_after_cursor_handler)
    remove(obj, 'handle_error', _connectable_error_handler)

def _can_operation_be_traced(conn, stmt_obj):
    '''
    Get whether an operation can be traced, depending on its
    connection or the statement being executed, having the latter
    the priority.
    '''
    if hasattr(stmt_obj, '_traced'):
        return stmt_obj._traced
    if hasattr(conn, '_traced'):
        return conn._traced

    return False

def _clear_traced(obj):
    '''
    Clear an object's decorated tracing fields,
    to prevent unintended further tracing.
    '''
    if hasattr(obj, '_parent_span'):
        del obj._parent_span
    if hasattr(obj, '_traced'):
        del obj._traced

def _set_traced_with_session(conn, session):
    '''
    Mark a connection to be traced with a session tracing information.
    '''
    conn._traced = True
    parent_span = get_parent_span(session)
    if parent_span is not None:
        conn._parent_span = parent_span

def _get_operation_name(stmt_obj):
    return stmt_obj.__visit_name__

def _normalize_stmt(statement):
    return statement.strip().replace('\n', '').replace('\t', '')

def _connectable_before_cursor_handler(conn, cursor,
                                       statement, parameters,
                                       context, executemany):
    if context.compiled is None: # PRAGMA
        return

    # Don't trace if trace_all is disabled
    # and the connection/statement wasn't marked explicitly.
    stmt_obj = context.compiled.statement
    if not (g_trace_all or _can_operation_be_traced(conn, stmt_obj)):
        return

    # Retrieve the parent span, if any,
    # either from the statement or inherited from the connection.
    parent_span = get_parent_span(stmt_obj)
    if parent_span is None:
        parent_span = get_parent_span(conn)

    # Start a new span for this query.
    name = _get_operation_name(stmt_obj)
    span = g_tracer.start_span(operation_name=name, child_of=parent_span)
    span.set_tag('component', 'sqlalchemy')
    span.set_tag('db.type', 'sql')
    span.set_tag('db.statement', _normalize_stmt(statement))

    stmt_obj._span = span

def _connectable_after_cursor_handler(conn, cursor,
                                      statement, parameters,
                                      context, executemany):
    if context.compiled is None: # PRAGMA
        return

    stmt_obj = context.compiled.statement
    span = get_span(stmt_obj)
    if span is None:
        return

    span.finish()

def _connectable_error_handler(exception_context):
    execution_context = exception_context.execution_context
    stmt_obj = execution_context.compiled.statement
    span = get_span(stmt_obj)
    if span is None:
        return

    span.set_tag('error', 'true')
    span.finish()

def _register_session_connection_event(session):
    '''
    Register connection/transaction and clean up events
    for our session only once, as adding/removing them
    seems an expensive operation.
    '''

    # Use 'after_being' as a mark to guess the events being handled.
    if contains(session, 'after_begin', _session_after_begin_handler):
        return

    # Have the connections inherit the tracing info
    # from the session (including parent span, if any).
    listen(session, 'after_begin', _session_after_begin_handler)

    # Plug post-operation clean up handlers.
    # The actual session commit/rollback is not traced by us.
    listen(session, 'after_commit', _session_before_commit_handler)
    listen(session, 'after_rollback', _session_rollback_handler)

def _session_after_begin_handler(session, transaction, conn):
    # It's only needed to pass down tracing information
    # if it was explicitly set.
    if get_traced(session):
        _set_traced_with_session(conn, session)

def _session_before_commit_handler(session):
    _clear_traced(session)

def _session_rollback_handler(session):
    _clear_traced(session)

