import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def _build_postgres_async_url() -> str:
    """
    Build an async PostgreSQL URL from environment variables.

    Env var strategy:
    - Prefer POSTGRES_URL if provided (may be a sync URL like postgresql://...).
      We will transform it to an async form by replacing scheme with postgresql+asyncpg://
      when needed.
    - Otherwise compose from POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB/POSTGRES_PORT,
      assuming host=localhost (common in this environment).

    NOTE: Environment variables are expected to be provided via the container .env.
    Do not hardcode credentials in code.
    """
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url:
        # Normalize to SQLAlchemy asyncpg URL
        if postgres_url.startswith("postgresql+asyncpg://"):
            return postgres_url
        if postgres_url.startswith("postgresql://"):
            return postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if postgres_url.startswith("postgres://"):
            return postgres_url.replace("postgres://", "postgresql+asyncpg://", 1)
        # If it's some other form, assume user supplied a valid SQLAlchemy URL already.
        return postgres_url

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRES_PORT")

    missing = [k for k, v in [("POSTGRES_USER", user), ("POSTGRES_PASSWORD", password), ("POSTGRES_DB", db), ("POSTGRES_PORT", port)] if not v]
    if missing:
        raise RuntimeError(
            "Database configuration missing required environment variables: "
            + ", ".join(missing)
            + ". Provide POSTGRES_URL or all of POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB/POSTGRES_PORT."
        )

    # Host is not provided via env in this project definition; localhost is correct for internal networking here.
    return f"postgresql+asyncpg://{user}:{password}@localhost:{port}/{db}"


_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


# PUBLIC_INTERFACE
def get_engine() -> AsyncEngine:
    """Get or create the shared AsyncEngine instance for the application."""
    global _engine, _sessionmaker
    if _engine is None:
        database_url = _build_postgres_async_url()
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            future=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


# PUBLIC_INTERFACE
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get or create the shared AsyncSession sessionmaker."""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


# PUBLIC_INTERFACE
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession."""
    session_maker = get_sessionmaker()
    async with session_maker() as session:
        yield session
