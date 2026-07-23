"""Villanyan-Agent 3.0 — Database setup (async SQLAlchemy 2.0 + aiosqlite)."""

import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./villanyan-agent.db")

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables (idempotent) with WAL mode + seed admin user."""
    from backend.core.models import User, CronJob, Reminder, CostRate, SecurityBaseline  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql("PRAGMA journal_mode=WAL"))
        await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin user if not exists
    from datetime import UTC, datetime
    from backend.core.security import hash_password
    import os
    password = os.getenv("VILLANYAN_PASSWORD", "")
    if password:
        from sqlalchemy import select
        async with async_session_factory() as session:
            try:
                result = await session.execute(select(User).where(User.role == "admin"))
                if not result.scalar_one_or_none():
                    admin = User(
                        username="admin",
                        password_hash=hash_password(password),
                        role="admin",
                    )
                    session.add(admin)
                    await session.commit()
            except Exception:
                pass

    # Seed default cost rates if empty
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(CostRate).limit(1))
            if not result.scalar_one_or_none():
                default_rates = [
                    CostRate(
                        model="deepseek-v4-flash",
                        price_in=0.14,
                        price_out=0.14,
                        currency="USD",
                        updated_at=datetime.now(UTC),
                    ),
                    CostRate(
                        model="deepseek-v4-pro",
                        price_in=0.435,
                        price_out=0.435,
                        currency="USD",
                        updated_at=datetime.now(UTC),
                    ),
                    CostRate(
                        model="qwen3.5:9b",
                        price_in=0.0,
                        price_out=0.0,
                        currency="USD",
                        updated_at=datetime.now(UTC),
                    ),
                    CostRate(
                        model="qwen2.5-coder:7b",
                        price_in=0.0,
                        price_out=0.0,
                        currency="USD",
                        updated_at=datetime.now(UTC),
                    ),
                    CostRate(
                        model="phi4:14b",
                        price_in=0.0,
                        price_out=0.0,
                        currency="USD",
                        updated_at=datetime.now(UTC),
                    ),
                ]
                for rate in default_rates:
                    session.add(rate)
                await session.commit()
        except Exception:
            pass


async def get_db():
    """FastAPI dependency — yields async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
