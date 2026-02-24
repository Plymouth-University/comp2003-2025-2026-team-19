# PLACEHOLDER SCRIPT FOR GENERATING API KEYS.
# Intended to be replaced by user authentication and key generation on the frontend in future.

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def generate_key(label="dev"):
    import secrets

    raw_key = f"sk_dev_{secrets.token_urlsafe(32)}"

    hashed_key = pwd_context.hash(raw_key)

    print(f"LABEL:   {label}")
    print(f"PREFIX:  {raw_key[:12]}")
    print(f"HASH:    {hashed_key}")
    print(f"RAW KEY: {raw_key}")


if __name__ == "__main__":
    generate_key()
