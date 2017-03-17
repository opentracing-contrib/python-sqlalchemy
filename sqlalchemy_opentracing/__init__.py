from sqlalchemy.event import listen, remove

g_tracer = None

def init_tracing(tracer):
    '''
    Set our global tracer.
    Tracer objects from our pyramid/flask/django libraries
    can be passed as well.
    '''
    global g_tracer
    if hasattr(tracer, '_tracer'):
        g_tracer = tracer._tracer
    else:
        g_tracer = tracer

def set_parent_span(stmt_obj, parent_span):
    '''
    Start tracing a given statement under
    a specific span.
    '''
    stmt_obj._parent_span = parent_span

def has_parent_span(stmt_obj):
    '''
    Get whether or not the statement has
    a parent span.
    '''
    return hasattr(stmt_obj, '_parent_span')

def get_span(stmt_obj):
    '''
    Get the span of a statement object, if any.
    '''
    return getattr(stmt_obj, '_span', None)

def register_connectable(obj):
    '''
    Register an object to have its events be traced.
    Any Connectable object is accepted, which
    includes Connection and Engine.
    '''
    listen(obj, 'before_cursor_execute', _before_cursor_handler)
    listen(obj, 'after_cursor_execute', _after_cursor_handler)
    listen(obj, 'handle_error', _error_handler)

def unregister_connectable(obj):
    '''
    Remove a connectable from having its events being
    traced.
    '''
    remove(obj, 'before_cursor_execute', _before_cursor_handler)
    remove(obj, 'after_cursor_execute', _after_cursor_handler)
    remove(obj, 'handle_error', _error_handler)

def _get_operation_name(stmt_obj):
    return stmt_obj.__visit_name__

def _normalize_stmt(statement):
    return statement.strip().replace('\n', '').replace('\t', '')

def _before_cursor_handler(conn, cursor, statement, parameters, context, executemany):
    if context.compiled is None: # PRAGMA
        return

    stmt_obj = context.compiled.statement
    parent_span = getattr(stmt_obj, '_parent_span', None)
    operation_name = _get_operation_name(stmt_obj)

    # Start a new span for this query.
    span = g_tracer.start_span(operation_name=operation_name, child_of=parent_span)

    span.set_tag('component', 'sqlalchemy')
    span.set_tag('db.type', 'sql')
    span.set_tag('db.statement', _normalize_stmt(statement))

    stmt_obj._span = span

def _after_cursor_handler(conn, cursor, statement, parameters, context, executemany):
    if context.compiled is None: # PRAGMA
        return

    stmt_obj = context.compiled.statement
    span = get_span(stmt_obj)
    if span is None:
        return

    span.finish()

def _error_handler(exception_context):
    execution_context = exception_context.execution_context
    stmt_obj = execution_context.compiled.statement
    span = get_span(stmt_obj)
    if span is None:
        return

    span.set_tag('error', 'true')
    span.finish()

