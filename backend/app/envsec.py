import argparse
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_bytes_file(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def write_text_file(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def encrypt_env(input_path: Path, output_path: Path, key: Optional[str]) -> None:
    if key is None:
        key = os.getenv("ENV_ENC_KEY")
    if not key:
        raise SystemExit("Missing key. Provide --key or set ENV_ENC_KEY.")
    f = Fernet(key.encode("utf-8"))
    plaintext = read_text_file(input_path).encode("utf-8")
    ciphertext = f.encrypt(plaintext)
    write_bytes_file(output_path, ciphertext)


def decrypt_env(input_path: Path, output_path: Optional[Path], key: Optional[str]) -> None:
    if key is None:
        key = os.getenv("ENV_ENC_KEY")
    if not key:
        raise SystemExit("Missing key. Provide --key or set ENV_ENC_KEY.")
    f = Fernet(key.encode("utf-8"))
    ciphertext = input_path.read_bytes()
    plaintext = f.decrypt(ciphertext).decode("utf-8")
    if output_path is None:
        print(plaintext)
    else:
        write_text_file(output_path, plaintext)


def encrypt_value(value: str, key: Optional[str]) -> str:
    if key is None:
        key = os.getenv("ENV_ENC_KEY")
    if not key:
        raise SystemExit("Missing key. Provide --key or set ENV_ENC_KEY.")
    f = Fernet(key.encode("utf-8"))
    token = f.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"ENC({token})"


def decrypt_value(value: str, key: Optional[str]) -> str:
    if key is None:
        key = os.getenv("ENV_ENC_KEY")
    if not key:
        raise SystemExit("Missing key. Provide --key or set ENV_ENC_KEY.")
    if value.startswith("ENC(") and value.endswith(")"):
        token = value[4:-1]
    else:
        token = value
    f = Fernet(key.encode("utf-8"))
    return f.decrypt(token.encode("utf-8")).decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt/decrypt .env files using Fernet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("gen-key", help="Generate a new encryption key")

    enc = sub.add_parser("encrypt", help="Encrypt a plaintext .env to .env.enc")
    enc.add_argument("input", type=Path, help="Path to plaintext .env")
    enc.add_argument("output", type=Path, help="Path to write .env.enc")
    enc.add_argument("--key", type=str, default=None, help="Fernet key (base64). If omitted, uses ENV_ENC_KEY")

    dec = sub.add_parser("decrypt", help="Decrypt .env.enc back to plaintext")
    dec.add_argument("input", type=Path, help="Path to .env.enc")
    dec.add_argument("-o", "--output", type=Path, default=None, help="Optional output plaintext path; prints to stdout if omitted")
    dec.add_argument("--key", type=str, default=None, help="Fernet key (base64). If omitted, uses ENV_ENC_KEY")

    # Value-level helpers
    val_enc = sub.add_parser("encrypt-value", help="Encrypt a single value and wrap as ENC(...)")
    val_enc.add_argument("value", type=str, help="Plaintext value to encrypt")
    val_enc.add_argument("--key", type=str, default=None, help="Fernet key (base64). If omitted, uses ENV_ENC_KEY")

    val_dec = sub.add_parser("decrypt-value", help="Decrypt a single value (accepts raw token or ENC(...))")
    val_dec.add_argument("value", type=str, help="Encrypted token or ENC(token)")
    val_dec.add_argument("--key", type=str, default=None, help="Fernet key (base64). If omitted, uses ENV_ENC_KEY")

    args = parser.parse_args()

    if args.cmd == "gen-key":
        print(generate_key())
    elif args.cmd == "encrypt":
        encrypt_env(args.input, args.output, args.key)
        print(f"Encrypted {args.input} -> {args.output}")
    elif args.cmd == "decrypt":
        decrypt_env(args.input, args.output, args.key)
        if args.output:
            print(f"Decrypted {args.input} -> {args.output}")
    elif args.cmd == "encrypt-value":
        print(encrypt_value(args.value, args.key))
    elif args.cmd == "decrypt-value":
        print(decrypt_value(args.value, args.key))


if __name__ == "__main__":
    main()


