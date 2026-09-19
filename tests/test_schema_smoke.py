from sqlalchemy import create_mock_engine
from sqlalchemy.orm import configure_mappers
from app.database.base import Base
import app.database.models

def test_all_mappers_and_postgresql_ddl_compile():
    configure_mappers()
    assert len(Base.metadata.tables) == 18
    statements = []
    engine = create_mock_engine('postgresql://', lambda sql, *a, **kw: statements.append(str(sql.compile(dialect=engine.dialect))))
    Base.metadata.create_all(engine, checkfirst=False)
    ddl = '\n'.join(statements)
    assert 'CREATE TABLE users' in ddl
    assert 'CREATE TABLE exam_answers' in ddl
    assert 'CREATE TYPE media_type' in ddl
