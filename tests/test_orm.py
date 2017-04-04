import unittest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

import sqlalchemy_opentracing
from .dummies import *

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)

class TestSQLAlchemyORM(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.session = sessionmaker(bind=self.engine)()
        User.metadata.create_all(self.engine)

        sqlalchemy_opentracing.register_engine(self.engine)

    def test_traced_simple(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        sqlalchemy_opentracing.set_traced(session)
        session.add(User(name='John Doe'))
        session.commit()

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual('insert', tracer.spans[0].operation_name)
        self.assertEqual(True, tracer.spans[0].is_finished)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'INSERT INTO users (name) VALUES (?)',
            'db.type': 'sql',
            'sqlalchemy.dialect': 'sqlite',
        })

    def test_traced_none(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        session.add(User(name='John Doe'))
        session.commit()

        self.assertEqual(0, len(tracer.spans))

    # test that when trace all is not True, we get nothing.
    # test mixing insert with select and insert
    def test_traced_all(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer, trace_all_queries=True)

        session = self.session
        session.add(User(name='John Doe'))
        session.add(User(name='Jason Bourne'))
        session.add(User(name='Foo Bar'))
        session.commit()

        self.assertEqual(3, len(tracer.spans))
        self.assertEqual(True, all(map(lambda x: x.operation_name == 'insert', tracer.spans)))
        self.assertEqual(True, all(map(lambda x: x.is_finished, tracer.spans)))

    def test_traced_error(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        # Don't trace this one.
        session = self.session
        session.add(User(name='John Doe', id=1))
        session.commit()

        # Trace this one.
        sqlalchemy_opentracing.set_traced(session)
        session.add(User(name='John Doe', id=1))
        try:
            session.commit()
        except IntegrityError:
            pass

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual('insert', tracer.spans[0].operation_name)
        self.assertEqual(True, tracer.spans[0].is_finished)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'INSERT INTO users (id, name) VALUES (?, ?)',
            'db.type': 'sql',
            'sqlalchemy.dialect': 'sqlite',
            'sqlalchemy.exception': 'UNIQUE constraint failed: users.id',
            'error': 'true',
        })

    def test_traced_parent(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        parent_span = DummySpan('parent')
        sqlalchemy_opentracing.set_parent_span(session, parent_span)
        session.query(User).all()
        session.query(User).all()
        session.commit()

        self.assertEqual(2, len(tracer.spans))
        self.assertEqual(True, all(map(lambda x: x.operation_name == 'select', tracer.spans)))
        self.assertEqual(True, all(map(lambda x: x.is_finished, tracer.spans)))
        self.assertEqual(True, all(map(lambda x: x.child_of == parent_span, tracer.spans)))

    def test_traced_text(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        span = DummySpan('parent span')
        sqlalchemy_opentracing.set_parent_span(session, span)
        session.execute('SELECT name FROM users')

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(tracer.spans[0].operation_name, 'textclause')
        self.assertEqual(tracer.spans[0].is_finished, True)
        self.assertEqual(tracer.spans[0].child_of, span)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'SELECT name FROM users',
            'db.type': 'sql',
            'sqlalchemy.dialect': 'sqlite',
        })

    def test_traced_text_error(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        span = DummySpan('parent span')
        sqlalchemy_opentracing.set_parent_span(session, span)
        try:
            session.execute('SELECT zipcode FROM addresses')
        except OperationalError:
            pass

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(tracer.spans[0].operation_name, 'textclause')
        self.assertEqual(tracer.spans[0].is_finished, True)
        self.assertEqual(tracer.spans[0].child_of, span)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'SELECT zipcode FROM addresses',
            'db.type': 'sql',
            'sqlalchemy.dialect': 'sqlite',
            'sqlalchemy.exception': 'no such table: addresses',
            'error': 'true',
        })

    def test_traced_after_commit(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        sqlalchemy_opentracing.set_traced(session)
        session.add(User(name='John Doe'))
        session.commit()
        self.assertEqual(1, len(tracer.spans))

        tracer.clear()

        # Issue a pair of statements,
        # making sure we are not tracing
        # the session's transaction anymore.
        session.add(User(name='Jason Bourne'))
        session.query(User).all()
        session.commit()
        self.assertEqual(0, len(tracer.spans))

    def test_traced_after_rollback(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        sqlalchemy_opentracing.set_traced(session)
        session.query(User).all()  # will be evaluated RIGHT AWAY
        session.add(User(name='John Doe')) # delayed (not committed)
        session.rollback()
        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(True, tracer.spans[0].is_finished)
        self.assertEqual('select', tracer.spans[0].operation_name)

        tracer.clear()

        # Rollback should have stopped
        # the tracing for this session
        session.query(User).all()
        session.add(User(name='Jason Bourne'))
        session.commit()
        self.assertEqual(0, len(tracer.spans))

    def test_traced_commit_repeat(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        parent_span1 = DummySpan('parent1')
        session = self.session
        sqlalchemy_opentracing.set_parent_span(session, parent_span1)
        session.add(User(name='John Doe'))
        session.commit()
        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(True, tracer.spans[0].is_finished)
        self.assertEqual(parent_span1, tracer.spans[0].child_of)

        # Register the session again for tracing,
        # now with a different parent span
        parent_span2 = DummySpan('parent2')
        sqlalchemy_opentracing.set_parent_span(session, parent_span2)
        session.add(User(name='Jason Bourne'))
        session.commit()
        self.assertEqual(2, len(tracer.spans))
        self.assertEqual(True, tracer.spans[1].is_finished)
        self.assertEqual(parent_span2, tracer.spans[1].child_of)

    @unittest.skip('SQLite doesnt properly handle savepoints')
    def test_traced_savepoint(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        sqlalchemy_opentracing.set_traced(session)
        session.add(User(name='John Doe'))

        session.begin_nested()
        session.add(User(name='Jason Bourne'))
        session.commit()

        session.add(User(name='Paris Texas'))
        session.commit()

        self.assertEqual(3, len(tracer.spans))
        self.assertEqual(True, all(map(lambda x: x.is_finished, tracer.spans)))

    def test_traced_bulk_insert(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        parent_span = DummySpan('parent')
        session = self.session
        sqlalchemy_opentracing.set_parent_span(session, parent_span)
        users = [User(name = 'User-%s' % i) for i in xrange(10)]
        session.bulk_save_objects(users)

        self.assertEqual(1, len(tracer.spans))
        self.assertEqual(True, tracer.spans[0].is_finished)
        self.assertEqual(parent_span, tracer.spans[0].child_of)
        self.assertEqual(tracer.spans[0].tags, {
            'component': 'sqlalchemy',
            'db.statement': 'INSERT INTO users (name) VALUES (?)',
            'db.type': 'sql',
            'sqlalchemy.dialect': 'sqlite',
        })

    def test_traced_clear_session(self):
        tracer = DummyTracer()
        sqlalchemy_opentracing.init_tracing(tracer)

        session = self.session
        sqlalchemy_opentracing.set_traced(session)
        session.add(User(name='John Doe'))
        session.add(User(name='Jason Bourne'))

        # Clear the tracing info right before committing.
        sqlalchemy_opentracing.clear_traced(session)
        session.commit()

        self.assertEqual(0, len(tracer.spans))

