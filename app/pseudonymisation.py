"""PRS pseudonymisation client — OPRF blinding and pseudonym derivation."""

import base64
import json
import logging

import pysodium
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings
from app.http_client import create_client

logger = logging.getLogger("headease.pseudonymisation")


def _oprf_blind(msg: bytes) -> tuple[bytes, bytes]:
    """Blind a message using ristretto255 OPRF.

    Equivalent to pyoprf.blind(): hash msg to ristretto255 point,
    multiply by random scalar.

    Returns (blind_factor, blinded_point).
    """
    # Hash message to a ristretto255 point
    point = pysodium.crypto_core_ristretto255_from_hash(
        pysodium.crypto_generichash(msg, outlen=64)
    )
    # Generate random scalar as blind factor
    blind_factor = pysodium.crypto_core_ristretto255_scalar_random()
    # Blind: point * scalar
    blinded_point = pysodium.crypto_scalarmult_ristretto255(blind_factor, point)
    return blind_factor, blinded_point


def create_blinded_input(
    personal_identifier: dict[str, str],
    recipient_organization: str,
    recipient_scope: str,
) -> tuple[str, str]:
    """Create a blinded input for the PRS.

    Args:
        personal_identifier: {"landCode": "NL", "type": "BSN", "value": "004895708"}
        recipient_organization: e.g. "ura:90000315"
        recipient_scope: e.g. "nationale-verwijsindex"

    Returns (blind_factor_b64, blinded_input_b64).
    """
    info = f"{recipient_organization}|{recipient_scope}|v1".encode("utf-8")
    pid = json.dumps(personal_identifier).encode("utf-8")
    logger.info("HKDF info: %s", info.decode())
    logger.info("HKDF pid:  %s", pid.decode())

    pseudonym = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    ).derive(pid)
    logger.info("HKDF pseudonym: %s", base64.urlsafe_b64encode(pseudonym).decode())

    blind_factor, blinded_input = _oprf_blind(pseudonym)

    return (
        base64.urlsafe_b64encode(blind_factor).decode(),
        base64.urlsafe_b64encode(blinded_input).decode(),
    )


def build_nvi_identifier(evaluated_output: str, blind_factor_b64: str) -> str:
    """Package PRS response + blind_factor into a base64url NVI identifier.

    The NVI subject.identifier.value is a base64url-encoded JSON object:
    {"evaluated_output": "<JWE>", "blind_factor": "<base64url blind_factor>"}
    """
    payload = json.dumps({
        "evaluated_output": evaluated_output,
        "blind_factor": blind_factor_b64,
    })
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode()


async def request_pseudonym(bsn: str) -> tuple[str, str]:
    """Request a pseudonym from the PRS for a given BSN.

    Uses POST /oprf/eval with the blinded input.
    Returns (nvi_identifier, blind_factor_b64) where nvi_identifier is ready
    to use as subject.identifier.value in a List resource.
    """
    personal_identifier = {"landCode": "NL", "type": "BSN", "value": bsn}
    # Recipient is the NVI, not us — PRS encrypts the result for the recipient
    recipient_organization = f"ura:{settings.nvi_ura_number}"
    recipient_scope = "nationale-verwijsindex"

    blind_factor_b64, blinded_input_b64 = create_blinded_input(
        personal_identifier, recipient_organization, recipient_scope
    )

    payload = {
        "encryptedPersonalId": blinded_input_b64,
        "recipientOrganization": recipient_organization,
        "recipientScope": recipient_scope,
    }

    from app.oauth import get_prs_token

    token = await get_prs_token()
    async with create_client() as client:
        resp = await client.post(
            f"{settings.prs_base_url}/oprf/eval",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        result = resp.json()

    evaluated_output = result["jwe"]
    nvi_identifier = build_nvi_identifier(evaluated_output, blind_factor_b64)
    return nvi_identifier, blind_factor_b64
