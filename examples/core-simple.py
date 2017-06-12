from sqlalchemy import MetaData, Table, Integer, String, Column, create_engine
from sqlalchemy.schema import CreateTable

import opentracing
import sqlalchemy_opentracing

# Your OpenTracing-compatible tracer here.
tracer = opentracing.Tracer()

if __name__ == '__main__':
    engine = create_engine('sqlite:///:memory:')

    sqlalchemy_opentracing.init_tracing(tracer)
    sqlalchemy_opentracing.register_engine(engine)

    metadata = MetaData()
    users = Table('users', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String),
    )
    creat = CreateTable(users)
    sqlalchemy_opentracing.set_traced(creat)

    with engine.begin() as conn:
        conn.execute(creat)

    tracer.flush()

