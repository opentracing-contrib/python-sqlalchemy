import os
from sqlalchemy import MetaData, Table, Integer, String, Column, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import lightstep
import sqlalchemy_opentracing

DB_LOCATION = '/tmp/simple.db'

tracer = lightstep.Tracer(
    component_name='sqlalchemy-orm-simple',
    access_token='{your_lightstep_token}'
)

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

    # Register the session for the current transaction.
    sqlalchemy_opentracing.set_traced(session)

    # Insert a new row.
    session.add(User(name='John Doe'))

    # Finish the commit.
    # This will stop tracing the session.
    session.commit()

