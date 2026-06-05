import streamlit as st
from auth import get_login_url, exchange_code
from extractor import extract_event_info
from calendar_api import get_calendar_service, get_or_create_calendar, add_event_to_calendar

# --- Page Config & Mobile Styling ---
st.set_page_config(page_title="EventSnap", page_icon="📅", layout="centered")

st.markdown("""
<style>
    /* Mobile-first constraints */
    .block-container {
        max-width: 600px;
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

st.markdown("<h1 class='title'>EventSnap 📸</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Capture interesting events directly to your calendar.</p>", unsafe_allow_html=True)

# --- Authentication ---
if "credentials" not in st.session_state:
    st.session_state["credentials"] = None

# Check query params for auth code
query_params = st.query_params
if "code" in query_params:
    try:
        # If code is a list (Streamlit older behavior), get the first item
        code_val = query_params["code"][0] if isinstance(query_params["code"], list) else query_params["code"]
        creds = exchange_code(code_val)
        st.session_state["credentials"] = creds
        # Clear the code from the URL
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Authentication failed: {e}")

is_logged_in = st.session_state["credentials"] is not None

if not is_logged_in:
    st.warning("Please log in to your Google Account to capture events.")

    # --- Temporary debug: masked secrets (REMOVE after fixing 403) ---
    def mask_secret(value: str) -> str:
        if len(value) <= 8:
            return value[:2] + "***" + value[-2:]
        return value[:4] + "***" + value[-4:]

    with st.expander("🔧 Debug: Loaded Secrets (masked)", expanded=True):
        try:
            cid = st.secrets["google_oauth"]["client_id"]
            csec = st.secrets["google_oauth"]["client_secret"]
            ruri = st.secrets["google_oauth"]["redirect_uri"]
            st.text(f"client_id:     {mask_secret(cid)}")
            st.text(f"client_secret: {mask_secret(csec)}")
            st.text(f"redirect_uri:  {ruri}")
        except Exception as e:
            st.error(f"Could not read secrets: {e}")
    # --- End temporary debug ---

    try:
        login_url = get_login_url()
        st.markdown(f'<a href="{login_url}" target="_self" rel="noreferrer noopener"><button style="width: 100%; border-radius: 8px; height: 50px; background-color: #4285F4; color: white; border: none; font-weight: bold; cursor: pointer;">Log In with Google</button></a>', unsafe_allow_html=True)
    except Exception as e:
        st.error("Failed to generate login URL. Make sure secrets are configured.")
        st.exception(e)
    st.stop()

# --- Main Interface ---
col1, col2 = st.columns([3, 1])
with col1:
    st.success("✅ Logged in successfully!")
with col2:
    if st.button("Log Out"):
        st.session_state["credentials"] = None
        st.rerun()

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
                details_list, scraped_texts, llm_prompts = extract_event_info(event_input)
                
                # Process each extracted event
                for idx, (details, scraped_text, llm_prompt) in enumerate(zip(details_list, scraped_texts, llm_prompts), start=1):
                    st.subheader(f"Event #{idx}")
                    # Show scraped raw text
                    with st.expander("Scraped Content (raw)", expanded=False):
                        st.code(scraped_text, language="text")
                    # Show LLM prompt for debugging
                    with st.expander("LLM System Prompt", expanded=False):
                        st.code(llm_prompt, language="text")
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
                        st.error(f"Failed to add Event #{idx} to calendar: {e}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
