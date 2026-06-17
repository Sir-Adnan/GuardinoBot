import base64
import binascii
import hashlib
from typing import Any

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from tortoise.fields import TextField
from tortoise.models import Model

import config

HASH_NAME = "SHA512"
IV_LENGTH = 12
ITERATION_COUNT = 65535
KEY_LENGTH = 32
SALT_LENGTH = 16
TAG_LENGTH = 16


def get_secret_key(password, salt):
    return hashlib.pbkdf2_hmac(
        HASH_NAME, password.encode(), salt, ITERATION_COUNT, KEY_LENGTH
    )


class AESSecret:
    secret_key = config.SECRET_KEY_STRING

    @classmethod
    def encrypt(cls, plain_msg: str) -> str:
        salt = get_random_bytes(SALT_LENGTH)
        iv = get_random_bytes(IV_LENGTH)

        cipher = AES.new(get_secret_key(cls.secret_key, salt), AES.MODE_GCM, iv)
        encrypted_message_byte, tag = cipher.encrypt_and_digest(
            plain_msg.encode("utf-8")
        )
        return bytes.decode(base64.b64encode(salt + iv + encrypted_message_byte + tag))

    @classmethod
    def decrypt(cls, cipher_msg: str) -> str:
        decoded_cipher_byte = base64.b64decode(cipher_msg)

        salt = decoded_cipher_byte[:SALT_LENGTH]
        iv = decoded_cipher_byte[SALT_LENGTH : (SALT_LENGTH + IV_LENGTH)]
        cipher = AES.new(get_secret_key(cls.secret_key, salt), AES.MODE_GCM, iv)

        return cipher.decrypt_and_verify(
            decoded_cipher_byte[(IV_LENGTH + SALT_LENGTH) : -TAG_LENGTH],
            decoded_cipher_byte[-TAG_LENGTH:],
        ).decode()


class PasswordField(TextField):
    def to_db_value(self, value: Any, instance: type[Model] | Model) -> Any:
        return AESSecret.encrypt(value) if value is not None else None

    def to_python_value(self, value: Any) -> Any:
        try:
            return (
                AESSecret.decrypt(super().to_python_value(value))
                if value is not None
                else None
            )
        except (binascii.Error, ValueError):
            return super().to_python_value(value)
