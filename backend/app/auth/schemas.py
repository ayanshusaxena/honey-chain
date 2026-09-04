"""Authentication API schemas."""

from typing import Literal

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Bearer access token returned after a successful login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
