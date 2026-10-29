from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[str]:
    """
    Verifies API Key for incoming agent telemetry and sensitive operations.
    If settings.API_KEY is not configured (None or empty), authentication is bypassed (permissive dev mode).
    If configured, validates against X-API-Key or Authorization Bearer header.
    """
    configured_key = settings.API_KEY
    if not configured_key:
        return x_api_key or "open-access"

    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1]
        else:
            provided_key = authorization.strip()

    if not provided_key or provided_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Please provide 'X-API-Key' header or 'Authorization: Bearer <key>'."
        )
    return provided_key

