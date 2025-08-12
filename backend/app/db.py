from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
import pg8000
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pathlib import Path

_executor = ThreadPoolExecutor(max_workers=10)

BASE_DIR = Path(__file__).resolve().parent.parent  # webapp/backend/app -> parent is webapp/backend

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()

class PgPool:
    def __init__(self, min_size=1, max_size=10):
        s = get_settings()
        self._q: Queue[pg8000.Connection] = Queue(maxsize=max_size)
        self._max = max_size
        self._created = 0
        self._cfg = dict(user=s.DB_USER, password=s.DB_PASSWORD, host=s.DB_HOST, port=s.DB_PORT, database=s.DB_NAME)
        for _ in range(min_size):
            self._q.put(self._connect())
            self._created += 1

    def _connect(self) -> pg8000.Connection:
        return pg8000.connect(**self._cfg)

    def getconn(self) -> pg8000.Connection:
        if self._q.empty() and self._created < self._max:
            self._created += 1
            return self._connect()
        return self._q.get()

    def putconn(self, conn: pg8000.Connection):
        self._q.put(conn)

_pool: Optional[PgPool] = None

def get_pool() -> PgPool:
    global _pool
    if _pool is None:
        _pool = PgPool(min_size=1, max_size=10)
    return _pool

# Helper to run blocking DB calls in thread pool

def run_db(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))
