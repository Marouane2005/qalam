from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from qalam.config import Settings

_engines: dict[str, Engine] = {}


class Base(DeclarativeBase):
    pass


def get_engine(settings: Settings) -> Engine:
    engine = _engines.get(settings.database_url)
    if engine is None:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        _engines[settings.database_url] = engine
    return engine


def session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(settings), expire_on_commit=False, class_=Session)


def session_scope(settings: Settings) -> Iterator[Session]:
    factory = session_factory(settings)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
