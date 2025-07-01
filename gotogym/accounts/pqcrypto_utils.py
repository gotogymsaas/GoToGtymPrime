"""Post-quantum crypto helpers using python-oqs."""
import base64
from pathlib import Path
import oqs

SIG_ALG = "Dilithium2"

_keypair_path = Path(__file__).resolve().parent / "pq_keys"
_keypair_path.mkdir(exist_ok=True)
_priv_file = _keypair_path / "private.key"
_pub_file = _keypair_path / "public.key"

if _priv_file.exists() and _pub_file.exists():
    private_key = _priv_file.read_bytes()
    public_key = _pub_file.read_bytes()
else:
    with oqs.Signature(SIG_ALG) as signer:
        public_key = signer.generate_keypair()
        private_key = signer.export_secret_key()
    _priv_file.write_bytes(private_key)
    _pub_file.write_bytes(public_key)

def sign_message(message: bytes) -> str:
    """Sign a message and return base64 signature."""
    with oqs.Signature(SIG_ALG, secret_key=private_key) as signer:
        signature = signer.sign(message)
    return base64.b64encode(signature).decode()

def verify_message(message: bytes, signature_b64: str) -> bool:
    signature = base64.b64decode(signature_b64)
    with oqs.Signature(SIG_ALG, public_key=public_key) as verifier:
        return verifier.verify(message, signature)
