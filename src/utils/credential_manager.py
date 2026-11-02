"""AES-256-GCM credential encryption and storage."""

import base64
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.utils.file_locking import locked_read_json, locked_write_json


class CredentialManager:
    """
    Manage encrypted credential storage using AES-256-GCM.

    Uses PBKDF2 for key derivation from master password.
    """

    # PBKDF2 parameters per research.md
    ITERATIONS = 200_000  # Per NIST SP 800-132 recommendations
    KEY_LENGTH = 32  # 256-bit key for AES-256
    NONCE_LENGTH = 12  # 96-bit nonce for GCM (standard)

    def __init__(self, credentials_dir: Path, master_password: str):
        """
        Initialize credential manager.

        Args:
            credentials_dir: Directory to store encrypted credentials
            master_password: Master password for key derivation
        """
        self.credentials_dir = credentials_dir
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.master_password = master_password
        self._key = self._derive_key()

    def _derive_key(self) -> bytes:
        """
        Derive encryption key from master password using PBKDF2-SHA256.

        Returns:
            256-bit encryption key
        """
        # Use username as salt for deterministic key derivation
        salt = b"playwright-workflows"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.ITERATIONS)
        key = kdf.derive(self.master_password.encode())
        return key

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: Text to encrypt

        Returns:
            Base64-encoded nonce + ciphertext + tag
        """

        cipher = AESGCM(self._key)
        nonce = os.urandom(self.NONCE_LENGTH)
        ciphertext = cipher.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext and encode as base64
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt AES-256-GCM ciphertext.

        Args:
            encrypted: Base64-encoded nonce + ciphertext + tag

        Returns:
            Decrypted plaintext

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        cipher = AESGCM(self._key)
        combined = base64.b64decode(encrypted)

        nonce = combined[: self.NONCE_LENGTH]
        ciphertext = combined[self.NONCE_LENGTH :]

        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def store_credential(
        self,
        key: str,
        username: str,
        password: str,
        metadata: Optional[dict] = None) -> None:
        """
        Store encrypted credential.

        Args:
            key: Unique identifier for this credential (e.g., 'test_user_login')
            username: Username/login
            password: Password
            metadata: Optional metadata (e.g., URL, description)
        """
        credential_data = {
            "username": self.encrypt(username),
            "password": self.encrypt(password),
            "metadata": metadata or {},
        }

        cred_file = self.credentials_dir / f"{key}.json"
        locked_write_json(cred_file, credential_data)

    def retrieve_credential(self, key: str) -> dict:
        """
        Retrieve and decrypt credential.

        Args:
            key: Credential identifier

        Returns:
            Dict with 'username', 'password', 'metadata'

        Raises:
            FileNotFoundError: If credential key not found
            cryptography.exceptions.InvalidTag: If decryption fails
        """
        cred_file = self.credentials_dir / f"{key}.json"

        if not cred_file.exists():
            raise FileNotFoundError(f"Credential not found: {key}")

        encrypted_data = locked_read_json(cred_file)

        return {
            "username": self.decrypt(encrypted_data["username"]),
            "password": self.decrypt(encrypted_data["password"]),
            "metadata": encrypted_data.get("metadata", {}),
        }

    def delete_credential(self, key: str) -> None:
        """Delete stored credential."""
        cred_file = self.credentials_dir / f"{key}.json"
        cred_file.unlink(missing_ok=True)

    def list_credentials(self) -> list:
        """List all stored credential keys."""
        return [f.stem for f in self.credentials_dir.glob("*.json")]
