import streamlit as st
import base64
import os
import logging
from auth import get_login_url, exchange_code, revoke_token
from extractor import extract_event_info
from calendar_api import get_calendar_service, get_or_create_calendar, add_event_to_calendar

logger = logging.getLogger(__name__)

# --- Page Config & Mobile Styling ---
st.set_page_config(page_title="EventSnap", page_icon="📅", layout="centered")

# --- Base URL Resolution & Privacy Policy Routing ---
try:
    base_url = st.secrets["google_oauth"]["redirect_uri"]
    if "?" in base_url:
        base_url = base_url.split("?")[0]
    if base_url.endswith("/"):
        base_url = base_url[:-1]
except Exception:
    base_url = "http://localhost:8501"

privacy_url = f"{base_url}/?page=privacy"

if st.query_params.get("page") == "privacy":
    st.title("Privacy Policy for EventSnap")
    st.write("This application is designed with privacy and security in mind. Please review how your data is handled below:")
    
    st.subheader("No Data Storage")
    st.write("The App does not store any data. The events are stored directly in YOUR Google calendar. Login is handled securely by Google Login (OAuth).")
    
    st.subheader("Public LLM Processing")
    st.write("The event URLs or Text you submit will be interpreted by a public LLM, in this case OpenAI. Do not submit highly sensitive personal text.")
    
    st.subheader("Dedicated Calendar")
    st.write("A new calendar named **'Events to Decide'** will be created and used to add events. Your main Calendar remains completely untouched. You can even use a different Google account if you want.")
    
    st.subheader("Full Control")
    st.write("You can revoke the permissions from your Google account anytime for EventSnap via your Google Account settings.")
    
    st.write("---")
    st.info("You can close this tab to return to the app.")
    st.stop()

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

try:
    icon_base64 = get_base64_image("calendar_icon.png")
    icon_html = f"<img src='data:image/png;base64,{icon_base64}' style='width: 48px; vertical-align: middle; margin-right: 12px; margin-bottom: 8px;'>"
except Exception:
    icon_html = ""



st.markdown("""
<style>
    /* Mobile-first constraints */
    .block-container {
        max-width: 900px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 50px;
        font-weight: 600;
        background-color: #4CAF50;
        color: white;
    }
    .stTextInput>div>div>input {
        border-radius: 8px;
    }
    .stTextArea>div>div>textarea {
        border-radius: 8px;
    }
    .title {
        text-align: center;
        font-family: 'Inter', sans-serif;
        color: #1E1E1E;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    /* Hide top header */
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- Authentication ---
if "credentials" not in st.session_state:
    st.session_state["credentials"] = None

# Check query params for auth code
query_params = st.query_params
if "code" in query_params:
    try:
        # If code is a list (Streamlit older behavior), get the first item
        code_val = query_params["code"][0] if isinstance(query_params["code"], list) else query_params["code"]
        state_val = query_params["state"][0] if isinstance(query_params["state"], list) else query_params.get("state")
        creds = exchange_code(code_val, state_val)
        st.session_state["credentials"] = creds
        # Clear the code and state from the URL
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        logger.exception("Authentication failed during code exchange.")
        st.error("Authentication failed. Please try logging in again.")

is_logged_in = st.session_state["credentials"] is not None

def render_header_and_banner():
    st.markdown(f"<h1 class='title'>{icon_html}EventSnap 📸</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Capture interesting events directly to your calendar.</p>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #e8f4fd 0%, #f0e6ff 100%);
        border-left: 4px solid #4285F4;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #333;
    ">
        <p style="margin: 0 0 0.4rem 0; font-weight: 600; font-size: 1rem;">
            Think of it as a Pocket where you throw in infos. about interesting events in a separate Google Calendar.
        </p>
        <p style="margin: 0 0 0.8rem 0; font-size: 0.85rem; color: #555; font-style: italic;">
            e.g. an email with 5 events at your club or uni? a Url from meetup.com or any other website? No Problem, just paste it.
        </p>
        <p style="margin: 0 0 0.4rem 0; font-weight: 600;">Key Features:</p>
        <ol style="margin: 0; padding-left: 1.4rem;">
            <li>The App does not store any data. The events are stored in YOUR Google calendar. Login is handled by Google OAuth.</li>
            <li>The event URLs or Text will be sent to OpenAI's API for processing. OpenAI retains API data for up to 30 days for abuse monitoring, but does not use it to train models. Do not paste highly sensitive personal information.</li>
            <li>It will create a new calendar "Events to Decide" and add events, not touching your main Calendar. You can even use a different Google account if you want.</li>
            <li>You can revoke the permissions from your Google account anytime for EventSnap.</li>
        </ol>
        <p style="margin-top: 1rem; text-align: center;">
            <a href="{privacy_url}" target="_blank" style="color: #4285F4; text-decoration: none; font-weight: 600;">🔒 View Privacy Policy</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

if not is_logged_in:
    render_header_and_banner()
    st.warning("Please log in to your Google Account to capture events.")

    try:
        login_url = get_login_url()
        st.markdown(f"### [🔗 Log In with Google]({login_url})")
    except Exception as e:
        logger.exception("Could not generate login URL.")
        st.error("Could not generate login URL. Please try again later.")

    st.stop()

# --- Top Right Header (Status & Logout) ---
col_space, col_status, col_logout = st.columns([6, 3, 2])
with col_status:
    st.markdown(
        "<div style='text-align: right; padding-top: 8px;'>"
        "<span style='background-color: #E8F5E9; color: #2E7D32; border: 1px solid #C8E6C9; padding: 6px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; white-space: nowrap;'>"
        "✅ Logged in"
        "</span>"
        "</div>",
        unsafe_allow_html=True
    )
with col_logout:
    st.markdown("""
        <style>
        /* Style the logout button in the top-right columns specifically */
        div[data-testid="column"]:nth-of-type(3) button {
            background-color: #d32f2f !important;
            color: white !important;
            height: 32px !important;
            padding: 0 10px !important;
            font-size: 0.8rem !important;
            border-radius: 6px !important;
            margin-top: 4px !important;
            font-weight: 600 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    if st.button("Log Out"):
        # Attempt to revoke the Google OAuth token before clearing session
        tokens = st.session_state.get("google_tokens")
        if tokens:
            # Prefer revoking the refresh token (revokes both); fall back to access token
            token_to_revoke = tokens.get("refresh_token") or tokens.get("access_token")
            if token_to_revoke:
                revoked = revoke_token(token_to_revoke)
                if revoked:
                    st.toast("Google access has been revoked.")
                else:
                    st.toast("Could not revoke Google access. You can revoke it manually in your Google Account security settings.")
        st.session_state["credentials"] = None
        st.session_state.pop("google_tokens", None)
        st.rerun()

# --- Main App Title & Banner ---
render_header_and_banner()

if "event_text" not in st.session_state:
    st.session_state["event_text"] = ""

def clear_event_text():
    st.session_state["event_text"] = ""

# Calculate dynamic height based on lines
current_text = st.session_state.get("event_text", "")
num_lines = current_text.count("\n") + 1
dynamic_height = max(150, min(num_lines * 24 + 40, 800))  # 150px min, 800px max

event_input = st.text_area(
    "Paste an event URL or description:",
    key="event_text",
    height=dynamic_height,
    placeholder="e.g. Photography workshop in Zurich on June 15, 6-9pm\nOR\nhttps://eventbrite.com/..."
)

# Align Capture on the left, Clear on the right
col_btn1, col_space, col_btn2 = st.columns([2, 6, 2])
with col_btn1:
    submitted = st.button("Capture Event", use_container_width=True)
with col_btn2:
    clear_btn = st.button("Clear", on_click=clear_event_text, use_container_width=True)
        
if submitted:
    if not event_input.strip():
        st.error("Please enter a URL or event description.")
    else:
        with st.spinner("Extracting event details..."):
            try:
                # 1. Extract Info
                details_list = extract_event_info(event_input)
                
                # Process each extracted event
                for idx, details in enumerate(details_list, start=1):
                    st.subheader(f"Event #{idx}")
                    # Show extracted preview (optional, for UX)
                    with st.expander("Extracted Details", expanded=False):
                        st.json(details.model_dump())
                    # 3. Save to Calendar for each event
                    try:
                        service = get_calendar_service(st.session_state["credentials"])
                        calendar_id = get_or_create_calendar(service)
                        event_link = add_event_to_calendar(service, calendar_id, details)
                        st.success(f"🎉 Event #{idx} added to 'Events to Decide' calendar! [View Event in Google Calendar]({event_link})")
                    except Exception as e:
                        logger.exception(f"Failed to add event #{idx} to calendar.")
                        st.error(f"Failed to add Event #{idx} to calendar. Please check your Google connection and try again.")
            except Exception as e:
                logger.exception("Error during event extraction.")
                st.error("An unexpected error occurred while processing your input. Please try again.")
