import pytest_asyncio

from app.database import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    yield
    await engine.dispose()
