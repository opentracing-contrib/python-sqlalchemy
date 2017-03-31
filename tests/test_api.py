import unittest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
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

    def test_init(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)
        self.assertEqual(tracer, sqlalchemy_opentracing.g_tracer)
        self.assertEqual(False, sqlalchemy_opentracing.g_trace_all)

    def test_init_subtracer(self):
        tracer = DummyTracer(with_subtracer=True)
        sqlalchemy_opentracing.init_tracing(tracer)
        self.assertEqual(tracer._tracer, sqlalchemy_opentracing.g_tracer)
        self.assertEqual(False, sqlalchemy_opentracing.g_trace_all)

    def test_init_traceall(self):
        sqlalchemy_opentracing.init_tracing(DummyTracer(), False)
        self.assertEqual(False, sqlalchemy_opentracing.g_trace_all)

        sqlalchemy_opentracing.init_tracing(DummyTracer(), True)
        self.assertEqual(True, sqlalchemy_opentracing.g_trace_all)

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

