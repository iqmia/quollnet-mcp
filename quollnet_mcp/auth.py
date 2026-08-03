from typing import Any

import jwt
from jwt import InvalidTokenError
from mcp.server.auth.provider import AccessToken, TokenVerifier


class QAuthTokenVerifier(TokenVerifier):
    def __init__(self, issuer_url: str, resource_uri: str, app_id: str, public_key: str) -> None:
        self.issuer_url = issuer_url
        self.resource_uri = resource_uri
        self.app_id = app_id
        self.public_key = public_key

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("typ") != "JWT":
                return None
            if header.get("kid") != self.app_id:
                return None

            claims: dict[str, Any] = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                audience=self.resource_uri,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nbf"]},
            )
            if (
                claims.get("token_use") != "mcp_access"
                or claims.get("client_app_id") != self.app_id
                or claims.get("sub") != claims.get("user_id")
                or not isinstance(claims.get("scope"), str)
            ):
                return None

            return AccessToken(
                token=token,
                client_id=self.app_id,
                scopes=claims["scope"].split(),
                expires_at=claims["exp"],
                resource=self.resource_uri,
                subject=claims["sub"],
                claims=claims,
            )
        except (InvalidTokenError, TypeError, ValueError, KeyError):
            return None
