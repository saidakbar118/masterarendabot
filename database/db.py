"""
database/db.py

Drops-in for the old aiosqlite version.
Uses asyncpg + a connection pool so many users work simultaneously.

The API is identical to before:
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

NOTE: asyncpg uses $1, $2 ... placeholders (not ?).
All queries in services already use $1/$2 because we updated them below.
"""
from __future__ import annotations

import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from loguru import logger

from config import DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX

# ── Single global pool ────────────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Create pool + create all tables + indexes. Call once at startup."""
    global _pool

    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=DB_POOL_MIN,
        max_size=DB_POOL_MAX,
        command_timeout=30,
    )
    logger.info(f"✅ PostgreSQL pool ready (min={DB_POOL_MIN} max={DB_POOL_MAX})")

    async with _pool.acquire() as conn:
        await _create_tables(conn)
    logger.info("✅ Tables ready")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Drop-in replacement for the old aiosqlite get_db().
    Yields a connection from the pool inside a transaction.
    Rolls back automatically on exception.
    """
    if _pool is None:
        raise RuntimeError("DB not initialized — call init_db() first")
    async with _pool.acquire() as conn:
        async with conn.transaction():
            yield conn


# ── Schema ────────────────────────────────────────────────────────────────────

async def _create_tables(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT    UNIQUE NOT NULL,
            full_name   TEXT      NOT NULL,
            shop_name   TEXT      NOT NULL,
            address     TEXT      NOT NULL,
            phone       TEXT      NOT NULL,
            is_active   BOOLEAN   NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tools (
            id          BIGSERIAL PRIMARY KEY,
            user_id     BIGINT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT      NOT NULL,
            quantity    INTEGER   NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            daily_price NUMERIC(14,2) NOT NULL DEFAULT 0,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, name)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rentals (
            id               BIGSERIAL PRIMARY KEY,
            user_id          BIGINT   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            customer_name    TEXT     NOT NULL,
            customer_address TEXT     NOT NULL,
            customer_phone   TEXT     NOT NULL,
            status           TEXT     NOT NULL DEFAULT 'active',
            rental_date      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rental_items (
            id                BIGSERIAL PRIMARY KEY,
            rental_id         BIGINT   NOT NULL REFERENCES rentals(id) ON DELETE CASCADE,
            tool_id           BIGINT   NOT NULL REFERENCES tools(id),
            quantity          INTEGER  NOT NULL,
            daily_price       NUMERIC(14,2) NOT NULL,
            returned_quantity INTEGER  NOT NULL DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id           BIGSERIAL PRIMARY KEY,
            rental_id    BIGINT   REFERENCES rentals(id),
            user_id      BIGINT   NOT NULL REFERENCES users(id),
            amount       NUMERIC(14,2) NOT NULL,
            payment_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS debts (
            id             BIGSERIAL PRIMARY KEY,
            user_id        BIGINT   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            customer_name  TEXT     NOT NULL,
            customer_phone TEXT     NOT NULL,
            amount         NUMERIC(14,2) NOT NULL DEFAULT 0,
            rental_id      BIGINT   REFERENCES rentals(id),
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sub_accounts (
            id          BIGSERIAL PRIMARY KEY,
            user_id     BIGINT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            telegram_id BIGINT    NOT NULL UNIQUE,
            added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Indexes for fast lookups
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_users_tgid    ON users(telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_sub_accounts  ON user_sub_accounts(telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_tools_user    ON tools(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_rentals_user  ON rentals(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_ritems_rental ON rental_items(rental_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_rent ON payments(rental_id)",
        "CREATE INDEX IF NOT EXISTS idx_debts_user    ON debts(user_id)",
    ]:
        await conn.execute(sql)
