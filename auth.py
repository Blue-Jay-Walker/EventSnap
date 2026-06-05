import secrets
import urllib.parse
import requests
import streamlit as st
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def get_login_url() -> str:
    """Build the Google OAuth authorization URL."""
    client_id = st.secrets["google_oauth"]["client_id"]
    redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

    state = secrets.token_urlsafe(32)
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


def exchange_code(code: str, returned_state: str) -> Credentials:
    """Exchange authorization code for Google OAuth credentials."""
    expected_state = st.session_state.get("oauth_state")
    if not expected_state or returned_state != expected_state:
        raise ValueError("Invalid OAuth state")

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