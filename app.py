import streamlit as st
import base64
import os
import logging
from auth import get_login_url, exchange_code, revoke_token
from extractor import extract_event_info
from calendar_api import get_calendar_service, get_or_create_calendar, add_event_to_calendar

logger = logging.getLogger(__name__)

# --- Mode Resolution & Configuration ---
app_mode = st.query_params.get("mode", "event")

if app_mode == "apartment":
    APP_NAME = "HomeSnap"
    APP_ICON = "🏠"
    DEFAULT_CALENDAR = "Apartment Visits"
    TEXT_PLACEHOLDER = "e.g. Viewing on Friday July 3rd at 6pm, rent is 2200 CHF at Bahnhofstrasse 10\nOR\nhttps://flatfox.ch/..."
    SUBTITLE = "Capture apartment search viewings directly to your calendar."
    
    BANNER_LEAD = "Think of it as a Pocket where you throw in details about apartment viewings and visits in a separate Google Calendar."
    BANNER_EG = "e.g. an email confirmation with viewing details? a URL from flatfox.ch, homegate.ch, or other listing sites? Just paste it."
    BANNER_FEAT_2 = "The apartment listing URLs or description text will be sent to OpenAI's API for processing. OpenAI retains API data for up to 30 days for abuse monitoring, but does not use it to train models. Do not paste highly sensitive personal information."
    BANNER_FEAT_3 = f"It will create a new calendar '{DEFAULT_CALENDAR}' and add viewings, not touching your main Calendar. You can even use a different Google account if you want."
else:
    APP_NAME = "EventSnap"
    APP_ICON = "📅"
    DEFAULT_CALENDAR = "Events to Decide"
    TEXT_PLACEHOLDER = "e.g. Photography workshop in Zurich on June 15, 6-9pm\nOR\nhttps://eventbrite.com/..."
    SUBTITLE = "Capture interesting events directly to your calendar."
    
    BANNER_LEAD = "Think of it as a Pocket where you throw in infos. about interesting events in a separate Google Calendar."
    BANNER_EG = "e.g. an email with 5 events at your club or uni? a Url from meetup.com or any other website? No Problem, just paste it."
    BANNER_FEAT_2 = "The event URLs or Text will be sent to OpenAI's API for processing. OpenAI retains API data for up to 30 days for abuse monitoring, but does not use it to train models. Do not paste highly sensitive personal information."
    BANNER_FEAT_3 = f"It will create a new calendar '{DEFAULT_CALENDAR}' and add events, not touching your main Calendar. You can even use a different Google account if you want."

# --- Page Config & Mobile Styling ---
st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="centered")

# --- Base URL Resolution & Privacy Policy Routing ---
try:
    base_url = st.secrets["google_oauth"]["redirect_uri"]
    if "?" in base_url:
        base_url = base_url.split("?")[0]
    if base_url.endswith("/"):
        base_url = base_url[:-1]
except Exception:
    base_url = "http://localhost:8501"

privacy_url = f"{base_url}/?page=privacy&mode={app_mode}"

if st.query_params.get("page") == "privacy":
    st.title(f"Privacy Policy for {APP_NAME}")
    st.write(f"This application is designed with privacy and security in mind. Please review how your data is handled below:")
    
    st.subheader("No Data Storage")
    if app_mode == "apartment":
        st.write(f"The App does not store any data. The apartment viewings are stored directly in YOUR Google calendar. Login is handled securely by Google Login (OAuth).")
    else:
        st.write(f"The App does not store any data. The events are stored directly in YOUR Google calendar. Login is handled securely by Google Login (OAuth).")
    
    st.subheader("Public LLM Processing")
    if app_mode == "apartment":
        st.write(f"The listing URLs or description text you submit will be interpreted by a public LLM, in this case OpenAI. Do not submit highly sensitive personal text.")
    else:
        st.write(f"The event URLs or Text you submit will be interpreted by a public LLM, in this case OpenAI. Do not submit highly sensitive personal text.")
    
    st.subheader("Dedicated Calendar")
    st.write(f"A new calendar named **'{DEFAULT_CALENDAR}'** will be created and used to add items. Your main Calendar remains completely untouched. You can even use a different Google account if you want.")
    
    st.subheader("Full Control")
    st.write(f"You can revoke the permissions from your Google account anytime for {APP_NAME} via your Google Account settings.")
    
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
    /* Style Clear button red */
    div.st-key-clearbtn button {
        background-color: #d32f2f !important;
        color: white !important;
        border: 1px solid #d32f2f !important;
    }
    div.st-key-clearbtn button:hover {
        background-color: #b71c1c !important;
        border: 1px solid #b71c1c !important;
    }
    /* Style Logout button orange */
    div.st-key-logoutbtn button {
        background-color: #FF9800 !important; /* Orange */
        color: white !important;
        height: 32px !important;
        padding: 0 10px !important;
        font-size: 0.8rem !important;
        border-radius: 6px !important;
        margin-top: 4px !important;
        font-weight: 600 !important;
        width: auto !important;
    }
    div.st-key-logoutbtn button:hover {
        background-color: #e65100 !important;
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
        
        # Clear the code and state from the URL, preserving the mode if present in state
        st.query_params.clear()
        if state_val and "__mode_apartment" in state_val:
            st.query_params["mode"] = "apartment"
            
        st.rerun()
    except Exception as e:
        logger.exception("Authentication failed during code exchange.")
        st.error("Authentication failed. Please try logging in again.")

is_logged_in = st.session_state["credentials"] is not None

def render_title():
    st.markdown(f"<h1 class='title'>{icon_html}{APP_NAME} {APP_ICON}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='subtitle'>{SUBTITLE}</p>", unsafe_allow_html=True)

def render_info_banner():
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #e8f4fd 0%, #f0e6ff 100%);
        border-left: 4px solid #4285F4;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1.5rem;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #333;
    ">
        <p style="margin: 0 0 0.4rem 0; font-weight: 600; font-size: 1rem;">
            {BANNER_LEAD}
        </p>
        <p style="margin: 0 0 0.8rem 0; font-size: 0.85rem; color: #555; font-style: italic;">
            {BANNER_EG}
        </p>
        <p style="margin: 0 0 0.4rem 0; font-weight: 600;">Key Features:</p>
        <ol style="margin: 0; padding-left: 1.4rem;">
            <li>The App does not store any data. The entries are stored in YOUR Google calendar. Login is handled by Google OAuth.</li>
            <li>{BANNER_FEAT_2}</li>
            <li>{BANNER_FEAT_3}</li>
            <li>You can revoke the permissions from your Google account anytime for {APP_NAME}.</li>
        </ol>
        <p style="margin-top: 1rem; text-align: center;">
            <a href="{privacy_url}" target="_blank" style="color: #4285F4; text-decoration: none; font-weight: 600;">🔒 View Privacy Policy</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

if not is_logged_in:
    render_title()
    render_info_banner()
    st.warning("Please log in to your Google Account to capture events.")

    try:
        login_url = get_login_url(app_mode)
        st.markdown(f"### [🔗 Log In with Google]({login_url})")
    except Exception as e:
        logger.exception("Could not generate login URL.")
        st.error("Could not generate login URL. Please try again later.")

    st.stop()

# --- Top Right Header (Logout Only) ---
col_space, col_logout = st.columns([9, 2])
with col_logout:
    if st.button("Log Out", key="logoutbtn"):
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

# --- Main App Title ---
render_title()

if "event_text" not in st.session_state:
    st.session_state["event_text"] = ""

def clear_event_text():
    st.session_state["event_text"] = ""

# Calculate dynamic height based on lines
current_text = st.session_state.get("event_text", "")
num_lines = current_text.count("\n") + 1
dynamic_height = max(150, min(num_lines * 24 + 40, 800))  # 150px min, 800px max

input_label = "Paste an apartment listing URL or viewing invitation details:" if app_mode == "apartment" else "Paste an event URL or description:"
button_label = "Capture Viewing" if app_mode == "apartment" else "Capture Event"

event_input = st.text_area(
    input_label,
    key="event_text",
    height=dynamic_height,
    placeholder=TEXT_PLACEHOLDER
)

# Align Clear on the left, Capture on the right
col_btn1, col_space, col_btn2 = st.columns([2, 6, 2])
with col_btn1:
    clear_btn = st.button("Clear", on_click=clear_event_text, use_container_width=True, key="clearbtn")
with col_btn2:
    submitted = st.button(button_label, use_container_width=True)
        
if submitted:
    input_error = "Please enter a URL or viewing details." if app_mode == "apartment" else "Please enter a URL or event description."
    spinner_msg = "Extracting viewing details..." if app_mode == "apartment" else "Extracting event details..."
    
    if not event_input.strip():
        st.error(input_error)
    else:
        with st.spinner(spinner_msg):
            try:
                # 1. Extract Info
                details_list = extract_event_info(event_input)
                
                # Process each extracted event
                for idx, details in enumerate(details_list, start=1):
                    entry_type = "Viewing" if app_mode == "apartment" else "Event"
                    st.subheader(f"{entry_type} #{idx}")
                    # 3. Save to Calendar for each event
                    try:
                        service = get_calendar_service(st.session_state["credentials"])
                        calendar_id = get_or_create_calendar(service, DEFAULT_CALENDAR)
                        event_link = add_event_to_calendar(service, calendar_id, details)
                        st.success(f"🎉 {entry_type} #{idx} added to '{DEFAULT_CALENDAR}' calendar! [View in Google Calendar]({event_link})")
                    except Exception as e:
                        logger.exception(f"Failed to add event #{idx} to calendar.")
                        st.error(f"Failed to add Event #{idx} to calendar. Please check your Google connection and try again.")
                    # Show extracted preview (optional, for UX)
                    with st.expander("Extracted Details", expanded=False):
                        st.json(details.model_dump())
            except Exception as e:
                logger.exception("Error during event extraction.")
                st.error("An unexpected error occurred while processing your input. Please try again.")

# --- Information Banner at the Bottom ---
render_info_banner()
