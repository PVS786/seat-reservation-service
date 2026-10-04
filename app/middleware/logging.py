import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import request_id_ctx_var

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = str(uuid.uuid4())

        token = request_id_ctx_var.set(req_id)
        start_time = time.time()

        logger.debug(
            "request started",
            extra={"method": request.method, "path": request.url.path},
        )

        try:
            response = await call_next(request)
            duration_ms = int((time.time() - start_time) * 1000)

            response.headers["X-Request-ID"] = req_id

            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            return response
        finally:
            request_id_ctx_var.reset(token)
