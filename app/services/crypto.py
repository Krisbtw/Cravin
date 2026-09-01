import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
# KEY must be a url-safe base64-encoded 32-byte key
# In production, fetch this securely (e.g., AWS KMS)
# Generate one if it doesn't exist for dev purposes
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_pii(data: str) -> str:
    if not data:
        return data
    return fernet.encrypt(data.encode()).decode()

def decrypt_pii(encrypted_data: str) -> str:
    if not encrypted_data:
        return encrypted_data
    return fernet.decrypt(encrypted_data.encode()).decode()
