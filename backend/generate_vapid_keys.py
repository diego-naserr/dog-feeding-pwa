"""Genera un par de claves VAPID para Web Push.

Uso:
    python generate_vapid_keys.py

Copiar la salida a las variables de entorno VAPID_PUBLIC_KEY y
VAPID_PRIVATE_KEY (en local: archivo .env; en Railway: Variables del servicio).
"""
import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()

    private_value = vapid.private_key.private_numbers().private_value
    private_raw = private_value.to_bytes(32, "big")

    public_raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962,
        format=PublicFormat.UncompressedPoint,
    )

    print("Agregá esto a tu .env (local) o a las Variables del servicio en Railway:\n")
    print(f"VAPID_PUBLIC_KEY={b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_raw)}")
    print("VAPID_SUBJECT=mailto:tu-email@ejemplo.com")


if __name__ == "__main__":
    main()
