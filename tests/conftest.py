import os
import pathlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import Base


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL environment variable is required for integration tests")
    return url


@pytest.fixture(scope="session")
def engine(database_url):
    engine = create_engine(database_url, future=True)
    Base.metadata.drop_all(bind=engine)

    alembic_cfg = Config(str(pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
