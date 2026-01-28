from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
from config import get_settings

settings = get_settings()

# Simple PIN validation for prototype - not for production use!
def verify_pin(plain_pin: str, stored_pin: str) -> bool:
    """Verify a PIN - simple comparison for prototype."""
    # For prototype: direct comparison or simple hash comparison
    if stored_pin.startswith('sha256:'):
        # If it's a simple hash, verify against hash
        pin_hash = 'sha256:' + hashlib.sha256(plain_pin.encode()).hexdigest()
        return pin_hash == stored_pin
    else:
        # Direct comparison for prototype
        return plain_pin == stored_pin


def get_pin_hash(pin: str) -> str:
    """Generate a simple hash for a PIN - for prototype only."""
    # Use simple SHA256 hash for prototype
    return 'sha256:' + hashlib.sha256(pin.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, datetime]:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt, expire


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
