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
    sqlalchemy_opentracing.register_connectable(engine) # A valid SQLAlchemy Engine object.

    with engine.begin() as conn:
        sel = select([users])
        sqlalchemy_opentracing.set_traced(sel)
        conn.execute(sel)

By default, only statements marked to be traced are taken into account (explicitly through set_traced() or implicitly when registering its parent span through set_parent_span()). Alternatively, you can enable tracing of all queries under the registered Engine/Connection:

.. code-block:: python

    sqlalchemy_opentracing.init_tracing(tracer, trace_all=True)
    sqlalchemy_opentracing.register_connectable(engine)

    # this statement will be traced too (without a parent span, though)
    with engine.begin() as conn:
        sel = select([users])
        conn.execute(sel)

Further information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

