"""
Async SQLAlchemy engine, session factory, and startup helpers.

Startup retry:
  wait_for_db() retries the connection with exponential back-off so the
  API pod doesn't crash-loop when Postgres is still initialising.

Graceful shutdown:
  dispose_engine() drains the connection pool cleanly.  Called from the
  lifespan context manager in main.py.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,           # verify connections before handing out
    echo=not settings.is_production,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def wait_for_db(
    retries: int | None = None,
    delay: float | None = None,
) -> None:
    """
    Wait until the database accepts connections.
    Raises RuntimeError if all retries are exhausted.
    """
    max_tries = retries if retries is not None else settings.database_connect_retries
    pause = delay if delay is not None else settings.database_connect_retry_delay

    for attempt in range(1, max_tries + 1):
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            logger.info("Database is ready (attempt %d/%d)", attempt, max_tries)
            return
        except Exception as exc:
            if attempt == max_tries:
                raise RuntimeError(
                    f"Database not ready after {max_tries} attempts: {exc}"
                ) from exc
            wait = min(pause * (2 ** (attempt - 1)), 30.0)
            logger.warning(
                "Database not ready (attempt %d/%d), retrying in %.1fs: %s",
                attempt, max_tries, wait, exc,
            )
            await asyncio.sleep(wait)


async def dispose_engine() -> None:
    """Drain and close all pooled connections. Call during shutdown."""
    await engine.dispose()
