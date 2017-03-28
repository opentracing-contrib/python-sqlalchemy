import unittest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import select

import sqlalchemy_opentracing
from .dummies import *

class TestSQLAlchemyCore(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.users_table = Table('users', MetaData(),
            Column('id', Integer, primary_key=True),
            Column('name', String),
        )
        sqlalchemy_opentracing.register_connectable(self.engine)

    def test_traced(self):
        tracer = DummyTracer()
        creat = CreateTable(self.users_table)

        sqlalchemy_opentracing.init_tracing(tracer)
        sqlalchemy_opentracing.set_traced(creat)
        self.engine.execute(creat)

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(tracer.spans[0].operation_name, 'create_table')
        self.assertEqual(tracer.spans[0].is_finished, True)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'CREATE TABLE users (id INTEGER NOT NULL, name VARCHAR, PRIMARY KEY (id))',
            'db.type': 'sql',
        })

    def test_traced_none(self):
        tracer = DummyTracer()
        creat = CreateTable(self.users_table)

        sqlalchemy_opentracing.init_tracing(tracer)
        self.engine.execute(creat)

        self.assertEqual(0, len(tracer.spans))

    def test_traced_all(self):
        tracer = DummyTracer()
        creat = CreateTable(self.users_table)

        sqlalchemy_opentracing.init_tracing(tracer, trace_all=True)
        self.engine.execute(creat)

        self.assertEqual(1, len(tracer.spans))

    def test_traced_error(self):
        tracer = DummyTracer()
        creat = CreateTable(self.users_table)

        sqlalchemy_opentracing.init_tracing(tracer)
        self.engine.execute(creat)
        self.assertEqual(0, len(tracer.spans))

        sqlalchemy_opentracing.set_traced(creat)
        try:
            self.engine.execute(creat)
        except OperationalError:
            pass # Do nothing - it's responsibility of OT to finish tracing it.

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(tracer.spans[0].is_finished, True)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'CREATE TABLE users (id INTEGER NOT NULL, name VARCHAR, PRIMARY KEY (id))',
            'db.type': 'sql',
            'error': 'true',
        })

    def test_unregister_connectable(self):
        tracer = DummyTracer()
        creat = CreateTable(self.users_table)

        sqlalchemy_opentracing.init_tracing(tracer, trace_all=True)
        self.engine.execute(creat)
        self.assertEqual(1, len(tracer.spans))

        tracer.clear()
        sqlalchemy_opentracing.unregister_connectable(self.engine)

        # Further events should cause no spans at all.
        sel = select([self.users_table])
        sqlalchemy_opentracing.set_traced(sel)
        self.engine.execute(sel)
        self.assertEqual(0, len(tracer.spans))

