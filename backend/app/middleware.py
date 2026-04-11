"""
Algeo Verify — API Logging Middleware
Automatically logs every API request to the APILog table.
"""

from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import get_session
from app.models.api_log import APILog


class APILoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip logging for static files, favicon, docs
        skip_paths = ["/favicon.ico", "/openapi.json", "/docs", "/redoc"]
        if request.url.path in skip_paths:
            return await call_next(request)

        response: Response = await call_next(request)

        # Log after response
        try:
            db = next(get_session())
            log = APILog(
                endpoint=request.url.path,
                method=request.method,
                request_time=datetime.now(timezone.utc),
                status_code=response.status_code,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            print(f"[LOG] Failed to log request: {e}")

        return response