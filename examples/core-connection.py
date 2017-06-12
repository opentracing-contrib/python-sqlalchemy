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
    ins = users.insert().values(name='John Doe')

    # All statements during this transaction will be traced.
    with engine.begin() as conn:
        sqlalchemy_opentracing.set_traced(conn)
        conn.execute(creat)
        conn.execute(ins)

    tracer.flush()

