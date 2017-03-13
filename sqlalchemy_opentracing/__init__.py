from sqlalchemy.event import listen
from sqlalchemy.engine import Connectable

import opentracing

g_tracer = None

def set_tracer(tracer):
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

def set_parent_span(stmt, parent_span):
    '''
    Start tracing a given statement under
    a specific span.
    '''
    stmt._parent_span = parent_span

def has_parent_span(stmt):
    '''
    Get whether or not the statement has
    a parent span.
    '''
    return hasattr(stmt, '_parent_span')

def _before_handler(conn, clauseelement, multiparams, params):
    parent_span = getattr(clauseelement, '_parent_span', None)
    span = tracer.start_span(operation_name='sql?', child_of=parent_span) # (xxx) operation name

    clauseelement._span = span

def _after_handler(conn, clauseelement, multiparams, params):
    if getattr(clauseelement, '_span', None) is None:
        return

    span = clauseelement._span
    span.finish()

def register_tracing(obj):
    '''
    Register an object to have its events be traced.
    '''
    if isinstance(obj, Connectable): # Engine or Connection instance.
        listen(obj, 'before_cursor_execute', _before_cursor_handler)
        listen(obj, 'after_cursor_execute', _after_cursor_handler)

    #elif isinstance(obj, MetaData): # Schema changes
    #    listen(obj, "before_create", _schema_before_handler)
    #    listen(obj, "after_create", _schema_after_handler)

