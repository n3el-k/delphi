from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False lets FastAPI's thread pool share the SQLite connection.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def create_db() -> None:
    import app.models  # noqa: F401  (registers the tables on SQLModel.metadata)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
