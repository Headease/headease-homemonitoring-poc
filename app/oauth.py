"""OAuth 2.0 client — obtain Bearer tokens for NVI and PRS using JWT client assertion."""

import base64
import hashlib
import time
import uuid

import jwt
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key

from app.config import settings
from app.http_client import create_client


def _load_cert(path) -> x509.Certificate:
    """Load a certificate from PEM or DER format."""
    data = path.read_bytes()
    if b"-----BEGIN CERTIFICATE-----" in data:
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def _load_cert_der_b64(path) -> str:
    """Load a certificate and return the DER bytes as base64 (for x5c)."""
    cert = _load_cert(path)
    der_bytes = cert.public_bytes(Encoding.DER)
    return base64.b64encode(der_bytes).decode("ascii")


def _cert_thumbprint_s256(path) -> str:
    """Compute SHA-256 thumbprint of a certificate (for cnf.x5t#S256)."""
    cert = _load_cert(path)
    der_bytes = cert.public_bytes(Encoding.DER)
    digest = hashlib.sha256(der_bytes).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _build_client_assertion(scope: str, target_audience: str) -> str:
    """Build a signed JWT client assertion for the OAuth token endpoint.

    - Signed with UZI private key (RS256)
    - x5c header contains UZI cert + intermediate
    - cnf.x5t#S256 contains LDN cert thumbprint
    """
    now = int(time.time())

    # Load private key
    key_data = settings.client_key_path.read_bytes()
    private_key = load_pem_private_key(key_data, password=None)

    # x5c: UZI cert chain (cert + intermediate)
    x5c = [
        _load_cert_der_b64(settings.uzi_cert_path),
        _load_cert_der_b64(settings.uzi_intermediate_cert_path),
    ]

    # LDN cert thumbprint for cnf
    ldn_thumbprint = _cert_thumbprint_s256(settings.ldn_cert_path)

    headers = {
        "alg": "RS256",
        "typ": "JWT",
        "x5c": x5c,
    }

    payload = {
        "iss": settings.ura_number,
        "sub": settings.ura_number,
        "aud": f"{settings.oauth_base_url}/oauth/token",
        "scope": scope,
        "target_audience": target_audience,
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "cnf": {
            "x5t#S256": ldn_thumbprint,
        },
    }

    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)


async def get_token(scope: str, target_audience: str) -> str:
    """Obtain a Bearer token from the OAuth server.

    Args:
        scope: e.g. "epd:write" or "prs:read"
        target_audience: e.g. "https://nvi.proeftuin.gf.irealisatie.nl"

    Returns the access_token string.
    """
    client_assertion = _build_client_assertion(scope, target_audience)

    form_data = {
        "grant_type": "client_credentials",
        "scope": scope,
        "target_audience": target_audience,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }

    async with create_client() as client:
        resp = await client.post(
            f"{settings.oauth_base_url}/oauth/token",
            data=form_data,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def get_nvi_token() -> str:
    """Get a token scoped for NVI."""
    return await get_token("epd:write", settings.nvi_base_url)


async def get_prs_token() -> str:
    """Get a token scoped for PRS."""
    return await get_token("prs:read", settings.prs_base_url)
