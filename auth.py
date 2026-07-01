import secrets
import base64
import logging
import urllib.parse
import requests
import streamlit as st
import streamlit.components.v1 as components
import hmac
import hashlib
import time
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

REVOKE_URL = "https://oauth2.googleapis.com/revoke"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def generate_secure_state(mode: str) -> str:
    """Generate a cryptographically signed state parameter to prevent CSRF statelessly."""
    client_secret = st.secrets["google_oauth"]["client_secret"]
    timestamp = int(time.time())
    random_part = secrets.token_urlsafe(16)
    payload = f"{random_part}__mode_{mode}__time_{timestamp}"
    
    # Compute HMAC-SHA256 signature using the client secret
    sig = hmac.new(client_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}__sig_{sig}"


def verify_secure_state(state: str) -> tuple[bool, str]:
    """Verify the signed state parameter and extract the mode.
    Returns (is_valid, mode)."""
    try:
        if not state:
            return False, "event"
            
        client_secret = st.secrets["google_oauth"]["client_secret"]
        
        # Split payload and signature
        if "__sig_" not in state:
            return False, "event"
            
        payload, sig = state.split("__sig_", 1)
        
        # Recompute signature
        expected_sig = hmac.new(client_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(sig, expected_sig):
            return False, "event"
            
        # Parse payload
        parts = payload.split("__")
        mode = "event"
        timestamp = 0
        for part in parts:
            if part.startswith("mode_"):
                mode = part.split("_", 1)[1]
            elif part.startswith("time_"):
                timestamp = int(part.split("_", 1)[1])
                
        # Expire after 15 minutes (900 seconds)
        if time.time() - timestamp > 900:
            return False, "event"
            
        return True, mode
    except Exception:
        return False, "event"


def get_login_url(mode: str = "event") -> str:
    """Build the Google OAuth authorization URL."""
    client_id = st.secrets["google_oauth"]["client_id"]
    redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

    state = generate_secure_state(mode)
    st.session_state["oauth_state"] = state

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    return f"{AUTH_BASE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, returned_state: str = None) -> Credentials:
    """Exchange authorization code for Google OAuth credentials."""
    # Verify the returned state cryptographically
    is_valid, mode = verify_secure_state(returned_state)
    if not is_valid:
        logger.warning("OAuth state verification failed — possible CSRF attempt or expired session.")
        raise ValueError("Authentication failed: OAuth state mismatch or expired login session. Please try logging in again.")

    data = {
        "code": code,
        "client_id": st.secrets["google_oauth"]["client_id"],
        "client_secret": st.secrets["google_oauth"]["client_secret"],
        "redirect_uri": st.secrets["google_oauth"]["redirect_uri"],
        "grant_type": "authorization_code",
    }

    response = requests.post(TOKEN_URL, data=data, timeout=30)
    response.raise_for_status()
    tokens = response.json()
    # Store dynamic expiration timestamp
    tokens["expiry_timestamp"] = time.time() + tokens.get("expires_in", 3600)

    granted_scopes = tokens.get("scope", "").split()

    creds = Credentials(
        token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=TOKEN_URL,
        client_id=st.secrets["google_oauth"]["client_id"],
        client_secret=st.secrets["google_oauth"]["client_secret"],
        scopes=granted_scopes or SCOPES,
    )

    st.session_state["google_tokens"] = tokens
    return creds


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired Google access token using a refresh token."""
    data = {
        "client_id": st.secrets["google_oauth"]["client_id"],
        "client_secret": st.secrets["google_oauth"]["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(TOKEN_URL, data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def revoke_token(token: str) -> bool:
    """Revoke a Google OAuth token (access or refresh) at Google's endpoint.
    Returns True if revocation succeeded, False otherwise."""
    try:
        response = requests.post(
            REVOKE_URL,
            params={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if response.status_code == 200:
            logger.info("Google OAuth token revoked successfully.")
            return True
        else:
            logger.warning(f"Token revocation returned status {response.status_code}.")
            return False
    except Exception:
        logger.exception("Failed to revoke Google OAuth token.")
        return False


def _xor_cipher(data: str) -> str:
    """XOR cipher for obfuscation/encryption using client_secret as key."""
    client_secret = st.secrets["google_oauth"]["client_secret"]
    key_bytes = client_secret.encode()
    data_bytes = data.encode()
    xor_bytes = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    return base64.b64encode(xor_bytes).decode()


def _xor_decipher(data_b64: str) -> str:
    """XOR decipher to decrypt cookie content."""
    client_secret = st.secrets["google_oauth"]["client_secret"]
    key_bytes = client_secret.encode()
    data_bytes = base64.b64decode(data_b64.encode())
    xor_bytes = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    return xor_bytes.decode()


def set_tokens_cookie(tokens: dict):
    """Write the tokens to a browser cookie using JavaScript (valid for 24 hours, encrypted)."""
    import json
    try:
        val_str = json.dumps(tokens)
        encrypted_val = _xor_cipher(val_str)
        components.html(f"""
        <script>
        document.cookie = "google_tokens=" + encodeURIComponent('{encrypted_val}') + "; path=/; max-age=86400; SameSite=Lax; Secure";
        </script>
        """, height=0)
    except Exception as e:
        logger.error(f"Failed to set tokens cookie: {e}")


def get_tokens_from_cookie(cookie_val: str) -> dict:
    """Decrypt and parse the tokens dictionary from the cookie value."""
    import json
    import urllib.parse
    if not cookie_val:
        return None
    try:
        cookie_decoded = urllib.parse.unquote(cookie_val)
        decrypted_str = _xor_decipher(cookie_decoded)
        return json.loads(decrypted_str)
    except Exception as e:
        logger.warning(f"Failed to decrypt tokens cookie: {e}")
        return None


def delete_tokens_cookie():
    """Delete the tokens browser cookie using JavaScript."""
    try:
        components.html("""
        <script>
        document.cookie = "google_tokens=; path=/; max-age=0; SameSite=Lax; Secure";
        </script>
        """, height=0)
    except Exception as e:
        logger.error(f"Failed to delete tokens cookie: {e}")


def check_and_refresh_tokens(tokens: dict) -> tuple[dict, bool]:
    """Check if the access token is close to expiry, and refresh it if needed.
    Returns (updated_tokens, was_refreshed)."""
    expiry = tokens.get("expiry_timestamp", 0)
    # If expiring in less than 5 minutes, refresh
    if expiry - time.time() < 300:
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise ValueError("No refresh token available.")
            
        refreshed_data = refresh_access_token(refresh_token)
        tokens["access_token"] = refreshed_data["access_token"]
        tokens["expiry_timestamp"] = time.time() + refreshed_data.get("expires_in", 3600)
        return tokens, True
    return tokens, False