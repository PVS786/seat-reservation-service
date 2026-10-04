import pytest
import pytest_asyncio
import json
import logging
import os
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from app.main import app
from app.logging_config import setup_logging

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_request_id_generated_and_returned(client: AsyncClient):
    import io
    from app.logging_config import JSONFormatter
    
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    
    logger = logging.getLogger("app.middleware.logging")
    logger.addHandler(handler)
    
    response = await client.get("/health/live")
    assert response.status_code == 200
    
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    
    logs = []
    for line in stream.getvalue().splitlines():
        try:
            logs.append(json.loads(line.strip()))
        except Exception:
            pass
            
    completion_logs = [log for log in logs if log.get("message") == "request completed"]
    assert len(completion_logs) == 1
    assert completion_logs[0]["request_id"] == req_id
    assert completion_logs[0]["path"] == "/health/live"
    
    logger.removeHandler(handler)

@pytest.mark.asyncio
async def test_request_id_preserved(client: AsyncClient):
    custom_id = "my-custom-request-id-123"
    response = await client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id

def test_default_log_level():
    # If LOG_LEVEL is not set, it should default to DEBUG
    with patch.dict(os.environ, {}, clear=True):
        setup_logging()
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

def test_env_log_level():
    with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}, clear=True):
        setup_logging()
        logger = logging.getLogger()
        assert logger.level == logging.INFO
