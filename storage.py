import datetime
from contextlib import contextmanager
from typing import Protocol, Self

import pydantic
import sqlalchemy
import sqlalchemy.exc
import sqlmodel


class StorageError(Exception):
    pass


class IntegrityError(StorageError):
    pass


class Item(sqlmodel.SQLModel, table=True):
    link: str = sqlmodel.Field(primary_key=True)
    id: str | None = None
    source: str
    title: str
    description: str | None = None
    date_posted: datetime.datetime | None = None
    date_modified: datetime.datetime | None = None
    date_added: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    meta: dict[str, str] = sqlmodel.Field(default={}, sa_type=sqlmodel.JSON)


class Storage(Protocol):
    def add(self, item: Item): ...
    def getNewItemCount(self) -> int: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback): ...


class SqliteStorage:
    engine: sqlalchemy.engine.Engine
    counter: int

    def __init__(self, filename: str):
        self.engine = sqlmodel.create_engine(f"sqlite:///{filename}")
        self.counter = 0
        Item.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        with sqlmodel.Session(self.engine) as session:
            yield session

    def items(self):
        with self.session() as session:
            statement = sqlmodel.select(Item).order_by(Item.date_added)
            res = session.exec(statement)
            for item in res.fetchall():
                yield item

    def add(self, item: Item):
        try:
            with self.session() as session:
                statement = sqlmodel.select(Item).where(Item.link == item.link)
                res = session.exec(statement)
                if exists := res.first():
                    if item.date_modified is None or (
                        exists.date_modified is not None
                        and exists.date_modified < item.date_modified
                    ):
                        raise IntegrityError(
                            f"link {item.link} already exists in database"
                        )
                    for field, value in item.model_dump().items():
                        if field == "link":
                            continue
                        setattr(exists, field, value)
                    item = exists

                session.add(item)
                session.commit()
                self.counter += 1
        except sqlalchemy.exc.IntegrityError as err:
            raise IntegrityError() from err

    def __enter__(self):
        self.counter = 0
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def getNewItemCount(self):
        return self.counter


class FakeStorage:
    def __init__(self):
        self.store: dict[str, Item] = {}
        self.counter: int = 0

    def add(self, item: Item):
        if item.link in self.store:
            breakpoint()
            raise KeyError(item.link)
        self.store[item.link] = item

    def __enter__(self):
        self.counter = 0
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass
