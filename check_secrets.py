import streamlit as st

def check_secrets():
    print("Checking Streamlit secrets...")
    try:
        oauth = st.secrets.get("google_oauth")
        if oauth:
            print("google_oauth section found.")
            client_id = oauth.get('client_id', '')
            client_secret = oauth.get('client_secret', '')
            redirect_uri = oauth.get('redirect_uri', '')
            
            print(f"client_id: {'***' + client_id[-6:] if len(client_id) > 6 else 'Missing or too short'}")
            print(f"client_secret: {'***' + client_secret[-4:] if len(client_secret) > 4 else 'Missing or too short'}")
            print(f"redirect_uri: {redirect_uri}")
        else:
            print("google_oauth section is MISSING in secrets.")
    except Exception as e:
        print(f"Error reading google_oauth secrets: {e}")

if __name__ == "__main__":
    check_secrets()
