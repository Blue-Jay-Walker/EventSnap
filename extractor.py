import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from urllib.parse import urlparse
import re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Structured output definition
class EventDetails(BaseModel):
    title: str = Field(description="The title of the event")
    start_date: Optional[str] = Field(description="Start date in YYYY-MM-DD format.")
    start_time: Optional[str] = Field(description="Start time normalized to 24-hour HH:MM format (e.g., '18:30' instead of '6:30pm' or '18.30'). Null if not mentioned.")
    end_date: Optional[str] = Field(description="End date in YYYY-MM-DD format. Null if not mentioned.")
    end_time: Optional[str] = Field(description="End time normalized to 24-hour HH:MM format. Null if not mentioned.")
    category: Literal["Tech", "AI", "Investing", "Social", "Games", "Outdoor activity", "Spiritual", "Apartment Viewing"] = Field(description="Event category. Use 'Apartment Viewing' if the content is an apartment viewing schedule or listing.")
    price: str = Field(description="Ticket price or 'Free'.")
    location: Optional[str] = Field(description="Physical location or 'Online'.")
    description: str = Field(description="Short description of the event.")
    source_url: Optional[str] = Field(description="Source URL if provided.")

def is_safe_url(url: str) -> bool:
    """Check if the URL is public and safe to scrape (prevents SSRF).
    Uses socket.getaddrinfo to resolve all A/AAAA records and rejects
    any address that is private, loopback, link-local, or multicast
    — covering both IPv4 and IPv6 ranges.
    """
    import socket
    import ipaddress
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        # getaddrinfo resolves both IPv4 and IPv6 addresses
        results = socket.getaddrinfo(hostname, None)
        if not results:
            return False

        for info in results:
            ip_str = info[4][0]
            # Strip IPv6 scope id if present (e.g. "fe80::1%eth0")
            ip_str = ip_str.split("%")[0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False

        return True
    except Exception:
        return False

def scrape_url(url: str) -> str:
    """Fetch page, extract visible text, and prepend title information."""
    if not is_safe_url(url):
        return f"Access denied: URL points to an unsafe or private network address."
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Title handling (page <title> and Open Graph)
        page_title = soup.title.string if soup.title else ""
        og_title = ""
        og_tag = soup.find("meta", property="og:title")
        if og_tag and og_tag.get("content"):
            og_title = og_tag["content"]
        combined_title = " ".join(filter(None, [page_title, og_title])).strip()
        # Extract structured data BEFORE decomposing scripts
        structured_data = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                structured_data.append(script.string)
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            structured_data.append(next_data.string)

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        # Collapse whitespace into clean lines
        lines = (ln.strip() for ln in text.splitlines())
        chunks = (ph.strip() for ln in lines for ph in ln.split("  "))
        cleaned = "\n".join(ch for ch in chunks if ch)
        
        if structured_data:
            # We truncate the structured data slightly to avoid massive blobs just in case
            structured_text = "\n".join(structured_data)[:15000]
            cleaned += "\n\nStructured Data:\n" + structured_text

        if combined_title:
            cleaned = combined_title + "\n" + cleaned
        return cleaned[:30000]
    except Exception as e:
        return f"Failed to scrape URL: {e}"

def is_url(text: str) -> bool:
    try:
        result = urlparse(text.strip())
        return all([result.scheme, result.netloc])
    except Exception:
        return False

class EventDetailsList(BaseModel):
    events: list[EventDetails]

def extract_event_info(input_text: str, model: str = "gpt-4.1-nano"):  # Or "gpt-4o-mini"
    """Extract event details using OpenAI.
    Returns list[EventDetails].
    Scrapes URLs and combines them with any accompanying text for unified LLM extraction."""
    # Find all URLs in the input
    lines = [ln.strip() for ln in input_text.splitlines() if ln.strip()]
    urls = [ln for ln in lines if is_url(ln)]

    # Limit to maximum 3 URLs per request to prevent token/request abuse
    if len(urls) > 3:
        st.warning("⚠️ To prevent API overload, only the first 3 URLs will be processed.")
        urls = urls[:3]

    def build_prompt():
        from zoneinfo import ZoneInfo
        zurich_tz = ZoneInfo("Europe/Zurich")
        now = datetime.now(zurich_tz)
        current_date_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M")
        current_day_name = now.strftime("%A")
        return (
            f"You are an event extraction assistant. Extract details from the following text. "
            f"Interpret dates/times as Europe/Zurich local time. "
            f"Today's reference date is {current_date_str} ({current_day_name}) and the current local time is {current_time_str} (Europe/Zurich timezone). "
            f"Use this reference date and time to resolve relative date/time descriptions like 'tomorrow', 'today', 'next Wednesday', etc. "
            f"If a year is missing, assume the year from today's date ({now.year}). "
            f"Provide dates in YYYY-MM-DD format. "
            f"Convert all start and end times to strict 24-hour 'HH:MM' format, cleaning up any separators like '.' or ';' and converting from AM/PM if necessary (e.g., '14:00' instead of '14.00' or '2pm'). "
            f"Do NOT invent times; return null if not present. "
            f"Check if the text or URL has information like rooms and rents; if so, it is about an apartment viewing/visit. "
            f"Apartment viewings can be provided as a combination of a URL (containing flat details) and text (containing the date/time of the visit). "
            f"If the entry is an apartment viewing/visit: "
            f"- Set the category to 'Apartment Viewing'. "
            f"- Set the price to the rent (e.g., '1500 CHF' or '1500/month'). "
            f"- Set the location to the apartment's physical address. "
            f"- Set the title to include the street name and number of the apartment (e.g., 'Apartment Viewing: [Street Name] [Number]')."
        )

    # Scrape all URLs
    scraped_contents = []
    for url in urls:
        scraped = scrape_url(url)
        scraped_contents.append(f"--- Scraped Content from {url} ---\n{scraped}")
        
    # Combine scraped contents and the original input
    combined_content = ""
    if scraped_contents:
        combined_content += "\n\n".join(scraped_contents) + "\n\n"
    
    combined_content += f"--- User Input ---\n{input_text}"
    
    system_prompt = build_prompt()
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_content}
            ],
            response_format=EventDetailsList,
        )
        details_list = completion.choices[0].message.parsed.events
        
        # Ensure source_url is populated and calculate default end times if missing
        for details in details_list:
            if urls and not details.source_url:
                details.source_url = urls[0]
                
            # If start_time is present but end_time is missing, calculate default end time
            if details.start_date and details.start_time and not details.end_time:
                try:
                    start_dt = datetime.strptime(f"{details.start_date} {details.start_time}", "%Y-%m-%d %H:%M")
                    
                    if details.category == "Apartment Viewing":
                        duration = timedelta(minutes=30)
                    else:
                        duration = timedelta(hours=2)
                        
                    end_dt = start_dt + duration
                    details.end_date = end_dt.strftime("%Y-%m-%d")
                    details.end_time = end_dt.strftime("%H:%M")
                except Exception:
                    pass
                
        return details_list
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise e
