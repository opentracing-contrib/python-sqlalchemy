import os
from sqlalchemy import MetaData, Table, Integer, String, Column, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import opentracing
import sqlalchemy_opentracing

DB_LOCATION = '/tmp/simple.db'

# Your OpenTracing-compatible tracer here.
tracer = opentracing.Tracer()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)

if __name__ == '__main__':
    if os.path.exists(DB_LOCATION):
        os.remove(DB_LOCATION) # cleanup

    engine = create_engine('sqlite:///%s' % DB_LOCATION)
    session = sessionmaker(bind=engine)()

    sqlalchemy_opentracing.init_tracing(tracer)
    sqlalchemy_opentracing.register_engine(engine)

    User.metadata.create_all(engine)

    # Create a parent span
    span = tracer.start_span('parent span')

    # Register the session for the current transaction.
    sqlalchemy_opentracing.set_parent_span(session, span)

    session.add(User(name='John Doe'))
    session.add(User(name='Jason Bourne'))

    users = session.query(User).all()
    for user in users:
        print user.name

    session.add(User(name='Who'))

    # Commit the session and close the parent span.
    session.commit()
    span.finish()

