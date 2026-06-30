import secrets
import logging
import urllib.parse
import requests
import streamlit as st
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

REVOKE_URL = "https://oauth2.googleapis.com/revoke"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def get_login_url(mode: str = "event") -> str:
    """Build the Google OAuth authorization URL."""
    client_id = st.secrets["google_oauth"]["client_id"]
    redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

    state = f"{secrets.token_urlsafe(32)}__mode_{mode}"
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
    expected_state = st.session_state.get("oauth_state")
    if expected_state and returned_state and returned_state != expected_state:
        st.warning(f"OAuth state mismatch: expected {expected_state}, got {returned_state}. Proceeding anyway...")

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