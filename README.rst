######################
SQLAlchemy Opentracing
######################

This package enables OpenTracing support for SQLAlchemy.

Installation
============

Run the following command::

    $ pip install sqlalchemy_opentracing

Getting started
===============

Please see the examples directory. Overall, basic usage requires that a tracer gets set, an Engine (or Connection) is registered, and statements get their parent spans assigned (if any):

.. code-block:: python

    import sqlalchemy_opentracing

    sqlalchemy_opentracing.init_tracing(tracer) # A OpenTracing compatible tracer.
    sqlalchemy_opentracing.register_engine(engine) # A valid SQLAlchemy Engine object.

    with engine.begin() as conn:
        sel = select([users])
        sqlalchemy_opentracing.set_traced(sel)
        conn.execute(sel)

By default, only statements marked to be traced are taken into account (explicitly through set_traced() or implicitly when registering its parent span through set_parent_span()). Alternatively, you can enable tracing of all queries under the registered Engine:

.. code-block:: python

    sqlalchemy_opentracing.init_tracing(tracer, trace_all_queries=True)
    sqlalchemy_opentracing.register_engine(engine)

    # this statement will be traced too (without a parent span, though)
    with engine.begin() as conn:
        sel = select([users])
        conn.execute(sel)

It is also possible to have all engines being registered automatically (independently of the `trace_all_queries` flag, which can be enabled or disabled):

.. code-block:: python

    # No need to call register_engine()
    sqlalchemy_opentracing.init_tracing(tracer, trace_all_engines=True)

    with engine.begin() as conn:
        sel = select([users])
        ...

This is equivalent to calling `register_engine` with the `sqlalchemy.engine.Engine` class.

The resulting spans will have an operation name related to the sql statement (such as `create-table` or `insert`), and will include exception information (if any), the dialect/backend (such as sqlite), and a few other hints.

Tracing under a Connection
===========================

It is possible to trace all statements being executed under a connection's transaction lifetime. For this, instead of marking a statement as traced, the connection is passed to set_traced() or set_parent_span():

.. code-block:: python

    parent_span = tracer.start_span('ParentSpan')
    conn = engine.connect()

    with conn.begin() as trans:
        sqlalchemy_opentracing.set_parent_span(conn, parent_span)

        # these three statements will be traced as children of
        # parent_span
        conn.execute(users.insert().values(name='John'))
        conn.execute(users.insert().values(name='Jason'))
        conn.execute(users.insert().values(name='Jackie'))

Either a commit or a rollback on a connection's transaction will finish its tracing. If the same Connection object is used afterwards, no tracing will be done for it (unless registered for tracing again). When using (emulated) nested transactions, the tracing needs to be marked at top-level transaction time, and tracing will happen for all statements under the nested transactions:

.. code-block:: python

    with conn.begin() as trans:
        sqlalchemy_opentracing.set_parent_span(conn, parent_span)
        conn.execute(users.insert().values(name='John'))

        with conn.begin() as nested_trans:
            # This statement will also be traced as
            # child of parent_span
            conn.execute(users.insert().values(name='Jason'))


Tracing under a Session (ORM)
=============================

It is also possible to trace all actual SQL statements happening during a Session's execution life time - that is, from being fresh to have its statements executed and committed (or rollbacked). For this, the Session object is passed to set_traced or set_parent_span():

.. code-block:: python

    parent_span = tracer.start_span('ParentSpan')
    session = Session()

    sqlalchemy_opentracing.set_parent_span(session, parent_span)
    try:
        session.add(User(name='Jackie'))
        session.commit()
    except IntegrityError:
        session.rollback()

Similar to what happens for Connection, either a commit or a rollback will finish its tracing, and further work on it will not be reported.

Tracing raw SQL statements
==========================

Executing raw SQL statements can be done through either a Connection or a Session, through their execute() method. Since there's no way to mark each statement individually, tracing them can be done through either tracing all statements, or through tracing a Connection's transaction or Session:

.. code-block:: python

    sqlalchemy_opentracing.set_parent_span(session, parent_span)

    # this statement will be traced as part of the session's execution
    session.execute('INSERT INTO users VALUES (?, ?)', 1, 'John')


Raw SQL statements will be traced having its operation name as `textclause`, to indicate their explicit text nature.

Manually cancel tracing
=======================

Sometimes no commit nor rollback may happen for a Connection or Session (for example, when doing bulk insertion/update). In this case, manually canceling tracing for an object can be done through clear_traced():

.. code-block:: python

    parent_span = tracer.start_span('ParentSpan')
    session = Session()

    sqlalchemy_opentracing.set_parent_span(session, parent_span)

    # this will generate tracing of a single INSERT statement.
    users = [User(name = 'User-%s' % i) for i in xrange(100)]
    session.bulk_save_objects(users)

    sqlalchemy_opentracing.clear_traced(session)

Manually canceling tracing will not clear any tracing already done - it will simply stop any further tracing for the current statement, Connection or Session object.

Further information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

