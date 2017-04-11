from sqlalchemy.engine import Connection, Engine
from sqlalchemy.event import contains, listen, remove
from sqlalchemy.orm import Session

g_tracer = None
g_trace_all_queries = False
g_trace_all_engines = False

def init_tracing(tracer, trace_all_engines=False, trace_all_queries=False):
    '''
    Set our global tracer.
    Tracer objects from our pyramid/flask/django libraries
    can be passed as well.
    '''
    global g_tracer, g_trace_all_engines, g_trace_all_queries

    if hasattr(tracer, '_tracer'):
        tracer = tracer._tracer
    else:
        tracer = tracer

    g_tracer = tracer
    g_trace_all_queries = trace_all_queries
    g_trace_all_engines = trace_all_engines

    if trace_all_engines:
        register_engine(Engine)

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

    if isinstance(obj, Session):
        # Session needs to have its connection/statements
        # decorated as soon as a connection is acquired.
        _register_session_events(obj)
    elif isinstance(obj, Connection):
        # Connection simply needs to be cleaned up
        # after commit/rollback.
        _register_connection_events(obj)

def clear_traced(obj):
    '''
    Clear an object's decorated tracing fields,
    to prevent unintended further tracing.
    '''
    if hasattr(obj, '_parent_span'):
        del obj._parent_span
    if hasattr(obj, '_traced'):
        del obj._traced

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

def register_engine(obj):
    '''
    Register an engine to have its events be traced.
    '''
    if g_tracer is None:
        raise RuntimeError('The tracer is not properly set')
    if g_trace_all_engines and obj != Engine:
        raise RuntimeError('Tracing all engines already')

    listen(obj, 'before_cursor_execute', _engine_before_cursor_handler)
    listen(obj, 'after_cursor_execute', _engine_after_cursor_handler)
    listen(obj, 'handle_error', _engine_error_handler)

def unregister_engine(obj):
    '''
    Remove an engine from having its events being traced.
    '''
    remove(obj, 'before_cursor_execute', _engine_before_cursor_handler)
    remove(obj, 'after_cursor_execute', _engine_after_cursor_handler)
    remove(obj, 'handle_error', _engine_error_handler)

def _clear_tracer():
    '''
    Set the tracer to None. For test cases usage.
    '''
    global g_tracer
    g_tracer = None

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

def _set_traced_with_session(conn, session):
    '''
    Mark a connection to be traced with a session tracing information.
    '''
    conn._traced = True
    parent_span = get_parent_span(session)
    if parent_span is not None:
        conn._parent_span = parent_span

def _get_operation_name(stmt_obj):
    if stmt_obj is None:
        # Match what the ORM shows when raw SQL
        # statements are invoked.
        return 'textclause'

    return stmt_obj.__visit_name__

def _normalize_stmt(statement):
    return statement.strip().replace('\n', '').replace('\t', '')

def _engine_before_cursor_handler(conn, cursor,
                                       statement, parameters,
                                       context, executemany):
    stmt_obj = None
    if context.compiled is not None:
        stmt_obj = context.compiled.statement

    # Don't trace if trace_all is disabled
    # and the connection/statement wasn't marked explicitly.
    if not (g_trace_all_queries or _can_operation_be_traced(conn, stmt_obj)):
        return

    # Don't trace PRAGMA statements coming from SQLite
    if stmt_obj is None and statement.startswith('PRAGMA'):
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
    span.set_tag('sqlalchemy.dialect', context.dialect.name)

    context._span = span

def _engine_after_cursor_handler(conn, cursor,
                                      statement, parameters,
                                      context, executemany):
    span = getattr(context, '_span', None)
    if span is None:
        return

    span.finish()

    if context.compiled is not None:
        clear_traced(context.compiled.statement)

def _engine_error_handler(exception_context):
    execution_context = exception_context.execution_context
    span = getattr(execution_context, '_span', None)
    if span is None:
        return

    exc = exception_context.original_exception
    span.set_tag('sqlalchemy.exception', str(exc))
    span.set_tag('error', 'true')
    span.finish()

    if execution_context.compiled is not None:
        clear_traced(execution_context.compiled.statement)

def _register_connection_events(conn):
    '''
    Register clean up events for our
    connection only once, as adding/removing them
    seems an expensive operation.
    '''

    # Use 'commit' as a mark to guess the events being handled.
    if contains(conn, 'commit', _connection_cleanup_handler):
        return

    # Plug post-operation clean up handlers.
    listen(conn, 'commit', _connection_cleanup_handler)
    listen(conn, 'rollback', _connection_cleanup_handler)

def _register_session_events(session):
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
    listen(session, 'after_commit', _session_cleanup_handler)
    listen(session, 'after_rollback', _session_cleanup_handler)

def _connection_cleanup_handler(conn):
    clear_traced(conn)

def _session_after_begin_handler(session, transaction, conn):
    # It's only needed to pass down tracing information
    # if it was explicitly set.
    if get_traced(session):
        _set_traced_with_session(conn, session)

def _session_cleanup_handler(session):
    clear_traced(session)

