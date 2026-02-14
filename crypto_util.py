from cryptography.fernet import Fernet


class Crypto:
    def __init__(self, fernet_key: str):
        self._fernet = Fernet(fernet_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
