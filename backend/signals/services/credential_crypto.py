"""
Fernet encryption for per-user Binance API credentials.

User-supplied API keys/secrets are stored encrypted at rest using a single
symmetric key sourced from the ``USER_API_KEY_ENC_KEY`` env var. The key is
generated once with ``Fernet.generate_key()`` and lives in the deployment
secret store (``.env`` locally, GitHub Actions secrets in CI/CD, server
``.env`` on the VPS). It must never be committed.

Failing to configure the env var crashes Django at startup rather than
silently producing an unusable system that would later corrupt stored
ciphertext on every key rotation attempt.
"""
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _load_fernet():
    """Load the Fernet cipher; raise loud at import if the key is missing/invalid."""
    raw = getattr(settings, 'USER_API_KEY_ENC_KEY', '') or ''
    if not raw:
        raise ImproperlyConfigured(
            "USER_API_KEY_ENC_KEY env var is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" "
            "and add it to your .env / GitHub secret. Do NOT commit it."
        )
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            f"USER_API_KEY_ENC_KEY is not a valid Fernet key: {exc}. "
            "Regenerate with Fernet.generate_key() and re-set the env var."
        ) from exc


_FERNET = _load_fernet()


def encrypt(plaintext):
    """Encrypt a string secret. Returns bytes suitable for ``BinaryField``."""
    if not isinstance(plaintext, str):
        raise TypeError("encrypt() expects a str")
    if not plaintext:
        raise ValueError("encrypt() refuses empty plaintext")
    return _FERNET.encrypt(plaintext.encode('utf-8'))


def decrypt(ciphertext):
    """Decrypt previously-encrypted bytes back to the original string."""
    if not ciphertext:
        raise ValueError("decrypt() refuses empty ciphertext")
    if isinstance(ciphertext, memoryview):
        ciphertext = bytes(ciphertext)
    try:
        return _FERNET.decrypt(ciphertext).decode('utf-8')
    except InvalidToken as exc:
        raise InvalidToken(
            "Failed to decrypt credential — the encryption key has changed "
            "or the ciphertext was tampered with. Affected rows must be re-entered."
        ) from exc


def hint(api_key):
    """Return a short non-secret display hint (last 4 chars). Never use as identity."""
    if not api_key or len(api_key) < 4:
        return ''
    return f"••••{api_key[-4:]}"
