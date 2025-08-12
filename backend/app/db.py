from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
import pg8000
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pathlib import Path
import os

try:
    # Optional dependency; only needed if using encrypted .env
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:  # pragma: no cover - treat as optional
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

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
    """
    Load settings. If an encrypted env file exists at `.env.enc` and
    the decryption key `ENV_ENC_KEY` is set, transparently decrypt it
    into environment variables prior to Pydantic loading.
    """
    enc_path = BASE_DIR / ".env.enc"
    if enc_path.exists():
        key = os.getenv("ENV_ENC_KEY")
        if not key:
            raise RuntimeError(
                "Encrypted env detected at .env.enc but ENV_ENC_KEY is not set."
            )
        if Fernet is None:
            raise RuntimeError(
                "cryptography is required to decrypt .env.enc. Please install requirements."
            )
        fernet = Fernet(key.encode("utf-8"))
        try:
            ciphertext = enc_path.read_bytes()
            plaintext = fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:  # type: ignore
            raise RuntimeError("Invalid ENV_ENC_KEY for decrypting .env.enc") from exc
        # Parse plaintext .env content and inject into process env
        for line in plaintext.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            value = value.strip()
            # Do not overwrite pre-set envs
            os.environ.setdefault(name, value)
    # Support per-variable encryption for DB credentials
    # Convention: wrap encrypted value as ENC(<fernet-token>)
    def _maybe_decrypt_env(name: str) -> None:
        value = os.getenv(name)
        if not value:
            return
        if value.startswith("ENC(") and value.endswith(")"):
            key = os.getenv("ENV_ENC_KEY")
            if not key:
                raise RuntimeError(
                    f"{name} is encrypted. Set ENV_ENC_KEY to decrypt."
                )
            if Fernet is None:
                raise RuntimeError(
                    "cryptography is required to decrypt encrypted env values."
                )
            token = value[4:-1]
            try:
                decrypted = Fernet(key.encode("utf-8")).decrypt(
                    token.encode("utf-8")
                ).decode("utf-8")
            except InvalidToken as exc:  # type: ignore
                raise RuntimeError(f"Failed to decrypt {name} with provided ENV_ENC_KEY") from exc
            os.environ[name] = decrypted

    # If a plaintext .env exists, pre-load its values for DB_USER/DB_PASSWORD and decrypt if needed.
    # Doing this before constructing Settings ensures environment variables override .env values inside Pydantic.
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name not in ("DB_USER", "DB_PASSWORD"):
                continue
            # If the process env already defines a clear value, keep it.
            if os.getenv(name) and not os.getenv(name, "").startswith("ENC("):
                continue
            os.environ[name] = value

    # Only decrypt sensitive fields if wrapped after potential pre-load
    _maybe_decrypt_env("DB_USER")
    _maybe_decrypt_env("DB_PASSWORD")
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
