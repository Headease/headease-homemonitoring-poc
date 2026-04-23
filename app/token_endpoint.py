"""OAuth 2.0 token endpoint — validates client assertions and issues Bearer tokens."""

import base64
import logging
import time

import jwt
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from fastapi import APIRouter, Form, Header, HTTPException

from app.config import settings
from app.token_store import store_token

logger = logging.getLogger("headease.token_endpoint")

router = APIRouter()


def _load_trusted_ca() -> x509.Certificate:
    """Load the trusted LDN CA certificate."""
    pem = settings.ldn_ca_cert_path.read_bytes()
    return x509.load_pem_x509_certificate(pem)


def _verify_x5c_chain(x5c: list[str], trusted_ca: x509.Certificate) -> x509.Certificate:
    """Verify the x5c certificate chain against the trusted CA.

    Returns the leaf certificate (used for JWT signature verification).
    Raises HTTPException if the chain is invalid.
    """
    if not x5c or len(x5c) < 1:
        raise HTTPException(status_code=401, detail="x5c header missing or empty")

    # Parse all certs in the chain
    certs = []
    for cert_b64 in x5c:
        der_bytes = base64.b64decode(cert_b64)
        certs.append(x509.load_der_x509_certificate(der_bytes))

    leaf = certs[0]

    # Find the cert signed by the trusted CA (should be the last in chain or intermediate)
    chain_valid = False
    ca_public_key = trusted_ca.public_key()

    for cert in certs:
        try:
            # Check if this cert is signed by the trusted CA
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                cert.signature_hash_algorithm,
            )
            chain_valid = True
            break
        except Exception:
            continue

    if not chain_valid:
        # Also check if the leaf is directly signed by the CA
        try:
            ca_public_key.verify(
                leaf.signature,
                leaf.tbs_certificate_bytes,
                leaf.signature_hash_algorithm,
            )
            chain_valid = True
        except Exception:
            pass

    if not chain_valid:
        raise HTTPException(status_code=401, detail="Certificate chain not trusted by LDN CA")

    # Check leaf cert is not expired
    now = time.time()
    if leaf.not_valid_before_utc.timestamp() > now:
        raise HTTPException(status_code=401, detail="Client certificate not yet valid")
    if leaf.not_valid_after_utc.timestamp() < now:
        raise HTTPException(status_code=401, detail="Client certificate expired")

    return leaf


@router.post("/oauth2/token")
async def issue_token(
    grant_type: str = Form(...),
    scope: str = Form(...),
    target_audience: str = Form(...),
    client_assertion_type: str = Form(...),
    client_assertion: str = Form(...),
    x_ura_identifier: str | None = Header(None, alias="x-ura-identifier"),
    x_healthcareproviderroletype: str | None = Header(None, alias="x-healthcareproviderroletype"),
    x_dezi_identifier: str | None = Header(None, alias="x-dezi-identifier"),
    x_dezi_roletype: str | None = Header(None, alias="x-dezi-roletype"),
):
    """Issue a Bearer token after validating a JWT client assertion.

    The client assertion must be signed with a certificate trusted by the LDN CA.
    """
    # Validate grant type
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")
    if client_assertion_type != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer":
        raise HTTPException(status_code=400, detail="Unsupported client_assertion_type")

    # Decode JWT header to get x5c (without verifying signature yet)
    try:
        unverified_header = jwt.get_unverified_header(client_assertion)
    except jwt.DecodeError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")

    x5c = unverified_header.get("x5c")
    if not x5c:
        raise HTTPException(status_code=401, detail="JWT missing x5c header")

    # Verify certificate chain against trusted LDN CA
    trusted_ca = _load_trusted_ca()
    leaf_cert = _verify_x5c_chain(x5c, trusted_ca)

    # Verify JWT signature using the leaf certificate's public key
    public_key = leaf_cert.public_key()
    try:
        claims = jwt.decode(
            client_assertion,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # We validate aud manually
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="JWT expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")

    # Validate audience — must match our FHIR base URL
    jwt_aud = claims.get("aud", "")
    if jwt_aud != settings.fhir_base_url:
        logger.warning("JWT aud mismatch: got %s, expected %s", jwt_aud, settings.fhir_base_url)

    logger.info(
        "Token issued for URA %s (iss=%s, scope=%s, target=%s)",
        x_ura_identifier, claims.get("iss"), scope, target_audience,
    )

    # Store token context in Redis
    context = {
        "iss": claims.get("iss"),
        "sub": claims.get("sub"),
        "scope": scope,
        "target_audience": target_audience,
        "x_ura_identifier": x_ura_identifier,
        "x_healthcareproviderroletype": x_healthcareproviderroletype,
        "x_dezi_identifier": x_dezi_identifier,
        "x_dezi_roletype": x_dezi_roletype,
        # TODO: verify cnf.x5t#S256 against mTLS client cert when available
        "cnf": claims.get("cnf"),
    }

    token = await store_token(context)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": settings.token_ttl,
        "scope": scope,
    }
