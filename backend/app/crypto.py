"""IMEI protection helpers.

Why two values are stored for one IMEI:
- encrypted copy (Fernet): reversible, so the owner could be shown it again later;
- HMAC: a one-way fingerprint made with a secret key. It lets the database
  enforce "one IMEI, one registration" without storing the IMEI itself.
  A plain SHA-256 would be unsafe here: there are only about 10^14 possible
  IMEIs, so an attacker with a database dump could try them all. The secret
  key in the HMAC prevents that.
"""

import hashlib
import hmac

from cryptography.fernet import Fernet

from app.config import get_settings


def is_valid_imei(imei: str) -> bool:
    """15 digits and a correct Luhn check digit."""
    if len(imei) != 15 or not imei.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(imei)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def encrypt_imei(imei: str) -> str:
    return Fernet(get_settings().imei_encryption_key.encode()).encrypt(imei.encode()).decode()


def decrypt_imei(token: str) -> str:
    return Fernet(get_settings().imei_encryption_key.encode()).decrypt(token.encode()).decode()


def imei_fingerprint(imei: str) -> str:
    key = get_settings().imei_hmac_key.encode()
    return hmac.new(key, imei.encode(), hashlib.sha256).hexdigest()


def mask_imei(last4: str) -> str:
    return "*" * 11 + last4


def proof_digest(device_id: str, code: str) -> str:
    """Keyed hash of an ownership code, bound to one device.

    Binding to the device id means a code issued for device A can never
    verify device B. The code itself is never stored.
    """
    key = get_settings().imei_hmac_key.encode()
    return hmac.new(key, f"proof:{device_id}:{code}".encode(), hashlib.sha256).hexdigest()
