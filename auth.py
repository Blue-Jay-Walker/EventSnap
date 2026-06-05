import streamlit as st
import requests
from google.oauth2.credentials import Credentials
import urllib.parse

SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly"
]

def get_login_url() -> str:
    """Generates the authorization URL for Google OAuth manually without PKCE."""
    client_id = st.secrets["google_oauth"]["client_id"]
    redirect_uri = st.secrets["google_oauth"]["redirect_uri"]
    scope_str = " ".join(SCOPES)
    
    # URL encode the parameters
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",
        "prompt": "consent"
    }
    query_string = urllib.parse.urlencode(params)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    return auth_url

def exchange_code(code: str) -> Credentials:
    """Exchanges the authorization code for credentials manually."""
    token_url = "https://oauth2.googleapis.com/token"
    
    data = {
        "code": code,
        "client_id": st.secrets["google_oauth"]["client_id"],
        "client_secret": st.secrets["google_oauth"]["client_secret"],
        "redirect_uri": st.secrets["google_oauth"]["redirect_uri"],
        "grant_type": "authorization_code"
    }
    
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    tokens = response.json()
    
    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=token_url,
        client_id=st.secrets["google_oauth"]["client_id"],
        client_secret=st.secrets["google_oauth"]["client_secret"],
        scopes=SCOPES
    )
    
    return creds
