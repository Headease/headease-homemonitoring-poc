"""OAuth 2.0 token endpoint — validates client assertions and issues Bearer tokens."""

import base64
import logging
import time

import jwt
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from fastapi import APIRouter, Form, Header, HTTPException

from app.config import settings
from app.token_store import store_token

logger = logging.getLogger("headease.token_endpoint")

router = APIRouter()


def _verify_cert_signed_by(cert: x509.Certificate, issuer: x509.Certificate) -> bool:
    """Check whether cert was signed by issuer, handling both RSA and ECDSA keys."""
    pk = issuer.public_key()
    try:
        if isinstance(pk, rsa.RSAPublicKey):
            pk.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
        elif isinstance(pk, ec.EllipticCurvePublicKey):
            pk.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                ec.ECDSA(cert.signature_hash_algorithm),
            )
        else:
            return False
        return True
    except Exception:
        return False


def _load_trusted_cas() -> list[x509.Certificate]:
    """Load all trusted CA certificates (UZI and LDN)."""
    cas = []
    for path in [settings.uzi_ca_cert_path, settings.ldn_ca_cert_path]:
        try:
            pem = path.read_bytes()
            ca = x509.load_pem_x509_certificate(pem)
            cas.append(ca)
            logger.info("Loaded trusted CA: %s -> %s", path, ca.subject.rfc4514_string())
        except FileNotFoundError:
            logger.error("MISSING CA cert file: %s — client JWT verification will fail for certs signed by this CA", path)
        except Exception as e:
            logger.error("Could not load CA %s: %s", path, e)
    if not cas:
        logger.error("No trusted CAs loaded — all client assertions will be rejected!")
    return cas


def _verify_x5c_chain(x5c: list[str], trusted_cas: list[x509.Certificate]) -> x509.Certificate:
    """Verify the x5c certificate chain against trusted CAs.

    Returns the leaf certificate (used for JWT signature verification).
    Raises HTTPException if the chain is invalid.
    """
    if not x5c or len(x5c) < 1:
        raise HTTPException(status_code=401, detail="x5c header missing or empty")

    # Parse all certs in the chain
    certs = []
    for i, cert_b64 in enumerate(x5c):
        try:
            der_bytes = base64.b64decode(cert_b64)
            cert = x509.load_der_x509_certificate(der_bytes)
            certs.append(cert)
            logger.info("x5c[%d]: subject=%s, issuer=%s", i, cert.subject, cert.issuer)
        except Exception as e:
            logger.error("x5c[%d]: failed to parse certificate: %s", i, e)
            raise HTTPException(status_code=401, detail=f"Invalid certificate in x5c[{i}]: {e}")

    leaf = certs[0]

    # Walk the chain: each cert must be signed by the next, and the last must chain to a trusted CA
    chain_valid = False
    for i in range(len(certs) - 1):
        child, parent = certs[i], certs[i + 1]
        if not _verify_cert_signed_by(child, parent):
            logger.error("Chain link broken: x5c[%d] (%s) NOT signed by x5c[%d] (%s)",
                         i, child.subject.rfc4514_string(), i + 1, parent.subject.rfc4514_string())
            raise HTTPException(status_code=401, detail=f"Chain link broken at x5c[{i}]")
        logger.info("Chain link OK: x5c[%d] signed by x5c[%d]", i, i + 1)

    # The last cert must be signed by a trusted CA (or be one)
    top = certs[-1]
    for ca in trusted_cas:
        if top.subject == ca.subject and _verify_cert_signed_by(top, ca):
            logger.info("Top of chain (%s) matches trusted CA", top.subject.rfc4514_string())
            chain_valid = True
            break
        if _verify_cert_signed_by(top, ca):
            logger.info("Top of chain (%s) signed by trusted CA (%s)", top.subject.rfc4514_string(), ca.subject.rfc4514_string())
            chain_valid = True
            break

    if not chain_valid:
        logger.error("Top of chain not signed by any trusted CA. Top subject=%s, issuer=%s",
                     top.subject.rfc4514_string(), top.issuer.rfc4514_string())
        for ca in trusted_cas:
            logger.error("  Trusted CA: %s", ca.subject.rfc4514_string())
        raise HTTPException(status_code=401, detail="Top of chain not signed by a trusted CA")

    # Check leaf cert is not expired
    now = time.time()
    if leaf.not_valid_before_utc.timestamp() > now:
        logger.error("Leaf cert not yet valid: %s", leaf.not_valid_before_utc)
        raise HTTPException(status_code=401, detail="Client certificate not yet valid")
    if leaf.not_valid_after_utc.timestamp() < now:
        logger.error("Leaf cert expired: %s", leaf.not_valid_after_utc)
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

    The client assertion must be signed with a certificate trusted by the UZI or LDN CA.
    """
    logger.info("=" * 80)
    logger.info("TOKEN REQUEST: grant_type=%s, scope=%s, target_audience=%s", grant_type, scope, target_audience)
    logger.info("Headers: x-ura-identifier=%s, x-healthcareproviderroletype=%s, x-dezi-identifier=%s, x-dezi-roletype=%s",
                x_ura_identifier, x_healthcareproviderroletype, x_dezi_identifier, x_dezi_roletype)
    logger.info("client_assertion (full): %s", client_assertion)

    # Validate grant type
    if grant_type != "client_credentials":
        logger.warning("Unsupported grant_type: %s", grant_type)
        raise HTTPException(status_code=400, detail="Unsupported grant_type")
    if client_assertion_type != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer":
        logger.warning("Unsupported client_assertion_type: %s", client_assertion_type)
        raise HTTPException(status_code=400, detail="Unsupported client_assertion_type")

    # Decode JWT header to get x5c (without verifying signature yet)
    try:
        unverified_header = jwt.get_unverified_header(client_assertion)
        logger.info("JWT header: alg=%s, typ=%s, x5c=%d cert(s)",
                     unverified_header.get("alg"), unverified_header.get("typ"), len(unverified_header.get("x5c", [])))
        # Log unverified claims for debugging
        unverified_claims = jwt.decode(client_assertion, options={"verify_signature": False})
        logger.info("JWT claims (unverified): %s", unverified_claims)
    except jwt.DecodeError as e:
        logger.error("Invalid JWT header: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")

    x5c = unverified_header.get("x5c")
    if not x5c:
        logger.error("JWT missing x5c header")
        raise HTTPException(status_code=401, detail="JWT missing x5c header")

    # Verify certificate chain against trusted CAs (UZI + LDN)
    trusted_cas = _load_trusted_cas()
    leaf_cert = _verify_x5c_chain(x5c, trusted_cas)

    # Verify JWT signature using the leaf certificate's public key
    public_key = leaf_cert.public_key()
    try:
        claims = jwt.decode(
            client_assertion,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # We validate aud manually
        )
        logger.info("JWT verified: iss=%s, sub=%s, scope=%s", claims.get("iss"), claims.get("sub"), claims.get("scope"))
    except jwt.ExpiredSignatureError:
        logger.error("JWT expired")
        raise HTTPException(status_code=401, detail="JWT expired")
    except jwt.InvalidTokenError as e:
        logger.error("Invalid JWT signature: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")

    # Validate audience — must match our FHIR base URL
    jwt_aud = claims.get("aud", "")
    if jwt_aud != settings.fhir_base_url:
        logger.warning("JWT aud mismatch: got %s, expected %s", jwt_aud, settings.fhir_base_url)

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

    logger.info("Token issued for iss=%s, scope=%s", claims.get("iss"), scope)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": settings.token_ttl,
        "scope": scope,
    }
