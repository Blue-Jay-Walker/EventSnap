# HomeSnap 🏠 & EventSnap 📸

A secure, stateless Streamlit web application that extracts events and apartment viewing details from text or URLs using OpenAI's GPT-4o, adding them directly to your Google Calendar.

---

## 🌟 Key Features

* **Multi-Mode Routing:** Access the app in **Event Mode (EventSnap)** or **Apartment Hunting Mode (HomeSnap)** via query parameters (`?mode=apartment`).
* **Smart LLM Extraction:** Automatically parses titles, prices/rents, locations, and descriptions. Uses your local timezone context to correctly resolve relative descriptions like *"Tomorrow at 18:30"* or *"Tonight"*.
* **Unified Context Merging:** Send a listing URL and a separate viewing date/time text block in the same paste; the app automatically scrapes the webpage and correlates it with your visit schedule into a single calendar entry.
* **Persistent Login:** A secure 24-hour cookie-based auto-login preserves your session across tab closures, silently refreshing expired tokens in the background.
* **Stateless & Private:** The app requests the least-privilege scope (`calendar.app.created`), meaning it **cannot** read or edit your primary personal calendar. No user credentials or event details are stored on any backend database.
* **Production-Ready Security:** Hardened against Cross-Site Request Forgery (CSRF) via cryptographic state signatures and protected from Server-Side Request Forgery (SSRF) during URL scraping.

---

## 🛠️ Local Setup & Configuration

Follow these steps to run the application locally:

### 1. Prerequisites
Ensure you have **Python 3.9+** installed.

### 2. Clone and Install Dependencies
```bash
# Clone the repository
git clone https://github.com/your-username/EventSnap.git
cd EventSnap

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Google OAuth Credentials
1. Go to the [Google Cloud Console API & Services](https://console.cloud.google.com/).
2. Create a new project.
3. Configure the **OAuth Consent Screen** (User Type: External, Publishing Status: Testing).
   * Request scope: `.../auth/calendar.app.created` (minimum scope to write app-owned events).
4. Go to **Credentials**, click **Create Credentials** -> **OAuth Client ID**.
   * Application type: Web application.
   * Authorized redirect URIs: Add `http://localhost:8501` (and your deployed Streamlit URL when hosting in production).

### 4. Create Streamlit Secrets
Create a file named `.streamlit/secrets.toml` in the project root:

```toml
OPENAI_API_KEY = "your-openai-api-key"

[google_oauth]
client_id = "your-google-oauth-client-id.apps.googleusercontent.com"
client_secret = "your-google-oauth-client-secret"
redirect_uri = "http://localhost:8501"
```

> [!WARNING]
> Never commit `.streamlit/secrets.toml` to GitHub! It is ignored by default in the project's `.gitignore` file.

### 5. Run the Application
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser. To access the Apartment Hunting mode, navigate to `http://localhost:8501/?mode=apartment`.

---

## 🔒 Security Measures

* **Stateless CSRF Prevention:** Integrates HMAC-SHA256 tokens using the client secret to sign redirect parameters, securing authentication statelessly without relying on fickle memory sessions.
* **Scraper SSRF Filtering:** Resolves target domain IPs and blocks requests attempting to access local networks (`localhost`) or cloud metadata endpoints (`169.254.169.254`).
* **API Abuse Controls:** Limits text inputs to 5,000 characters, scrapes a maximum of 3 URLs per request, and enforces a 5-second cooldown alongside session caps to prevent automated token depletion.

---

## 📄 License
This project is licensed under the MIT License.
