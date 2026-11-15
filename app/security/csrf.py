import secrets

from fastapi import HTTPException, Request, Header, status


def create_csrf_token(request: Request) -> str:

    token = request.session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token

    return token


async def verify_csrf_token(
    request: Request,
    x_csrf_token: str | None = Header(default=None)
):

    session_token = request.session.get("csrf_token")

    if not session_token or not x_csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token is missing"
        )

    if not secrets.compare_digest(
        session_token,
        x_csrf_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token"
        )