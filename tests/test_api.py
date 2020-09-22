import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import CreateTable

import sqlalchemy_opentracing
from .dummies import *

class TestGlobalCalls(unittest.TestCase):
    def setUp(self):
        metadata = MetaData()
        self.users_table = Table('users', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String),
        )

    def tearDown(self):
        sqlalchemy_opentracing._clear_tracer()

    @patch('sqlalchemy_opentracing.register_engine')
    def test_init(self, mock_register):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)
        self.assertEqual(tracer, sqlalchemy_opentracing.g_tracer)
        self.assertEqual(True, sqlalchemy_opentracing.g_trace_all_queries)

    @patch('sqlalchemy_opentracing.register_engine')
    def test_init_subtracer(self, mock_register):
        tracer = DummyTracer(with_subtracer=True)
        sqlalchemy_opentracing.init_tracing(tracer)
        self.assertEqual(tracer._tracer, sqlalchemy_opentracing.g_tracer)
        self.assertEqual(True, sqlalchemy_opentracing.g_trace_all_queries)

    @patch('sqlalchemy_opentracing.register_engine')
    def test_init_trace_all_queries(self, mock_register):
        sqlalchemy_opentracing.init_tracing(DummyTracer(), trace_all_queries=False)
        self.assertEqual(False, sqlalchemy_opentracing.g_trace_all_queries)

        sqlalchemy_opentracing.init_tracing(DummyTracer(), trace_all_queries=True)
        self.assertEqual(True, sqlalchemy_opentracing.g_trace_all_queries)

    @patch('sqlalchemy_opentracing.register_engine')
    def test_init_trace_all_engines(self, mock_register):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)
        self.assertEqual(1, mock_register.call_count)

        sqlalchemy_opentracing.init_tracing(tracer, trace_all_engines=False)
        self.assertEqual(1, mock_register.call_count) # Not called

        sqlalchemy_opentracing.init_tracing(tracer, trace_all_engines=True)
        self.assertEqual(2, mock_register.call_count) # Called again

    def test_traced_property(self):
        stmt_obj = CreateTable(self.users_table)
        sqlalchemy_opentracing.set_traced(stmt_obj)
        self.assertEqual(True, sqlalchemy_opentracing.get_traced(stmt_obj))

    def test_has_parent(self):
        span = DummySpan()
        stmt = CreateTable(self.users_table)
        sqlalchemy_opentracing.set_parent_span(stmt, span)
        self.assertEqual(True, sqlalchemy_opentracing.has_parent_span(stmt))
        self.assertEqual(span, sqlalchemy_opentracing.get_parent_span(stmt))

    def test_has_parent_none(self):
        stmt = CreateTable(self.users_table)
        sqlalchemy_opentracing.set_traced(stmt)
        self.assertEqual(False, sqlalchemy_opentracing.has_parent_span(stmt))
        self.assertEqual(None, sqlalchemy_opentracing.get_parent_span(stmt))

    def test_register_no_tracer(self):
        engine = create_engine('sqlite:///:memory:')
        with self.assertRaises(RuntimeError):
            sqlalchemy_opentracing.register_engine(engine)

    def test_register_dup(self):
        engine = create_engine('sqlite:///:memory:')
        sqlalchemy_opentracing.init_tracing(DummyTracer(), trace_all_engines=True)
        with self.assertRaises(RuntimeError):
            sqlalchemy_opentracing.register_engine(engine)

        # Manually clear the Engine from listening events.
        sqlalchemy_opentracing.unregister_engine(Engine)

