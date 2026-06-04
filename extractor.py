import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from urllib.parse import urlparse
import re
from datetime import datetime

# Structured output definition
class EventDetails(BaseModel):
    title: str = Field(description="The title of the event")
    start_date: Optional[str] = Field(description="Start date in YYYY-MM-DD format.")
    start_time: Optional[str] = Field(description="Start time normalized to 24-hour HH:MM format (e.g., '18:30' instead of '6:30pm' or '18.30'). Null if not mentioned.")
    end_date: Optional[str] = Field(description="End date in YYYY-MM-DD format. Null if not mentioned.")
    end_time: Optional[str] = Field(description="End time normalized to 24-hour HH:MM format. Null if not mentioned.")
    category: Literal["Tech", "AI", "Investing", "Social", "Games", "Outdoor activity", "Spiritual"] = Field(description="Event category.")
    price: str = Field(description="Ticket price or 'Free'.")
    location: Optional[str] = Field(description="Physical location or 'Online'.")
    description: str = Field(description="Short description of the event.")
    source_url: Optional[str] = Field(description="Source URL if provided.")

def scrape_url(url: str) -> str:
    """Fetch page, extract visible text, and prepend title information."""
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
        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        # Collapse whitespace into clean lines
        lines = (ln.strip() for ln in text.splitlines())
        chunks = (ph.strip() for ln in lines for ph in ln.split("  "))
        cleaned = "\n".join(ch for ch in chunks if ch)
        if combined_title:
            cleaned = combined_title + "\n" + cleaned
        return cleaned[:20000]
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

def extract_event_info(input_text: str):
    """Extract event details using OpenAI.
    Returns (list[EventDetails], list[str] raw_texts, list[str] system_prompts).
    Handles multiple URLs and free‑text (multiple events)."""
    # Split input into non‑empty lines
    lines = [ln.strip() for ln in input_text.splitlines() if ln.strip()]
    
    # Separate URLs from normal text
    urls = [ln for ln in lines if is_url(ln)]
    # All non-url text combined as a single free-text block
    free_text_block = "\n".join([ln for ln in lines if not is_url(ln)]).strip()

    details_list = []
    raw_texts = []
    prompts = []

    def build_prompt():
        current_year = datetime.now().year
        return (
            f"You are an event extraction assistant. Extract details from the following text. "
            f"Interpret dates/times as Europe/Zurich local time. "
            f"If a year is missing, assume {current_year}. "
            f"Provide dates in YYYY-MM-DD format. "
            f"Convert all start and end times to strict 24-hour 'HH:MM' format, cleaning up any separators like '.' or ';' and converting from AM/PM if necessary (e.g., '14:00' instead of '14.00' or '2pm'). "
            f"Do NOT invent times; return null if not present."
        )

    # 1. Process URLs individually
    for url in urls:
        scraped = scrape_url(url)
        raw = f"Content scraped from {url}:\n\n" + scraped

        system_prompt = build_prompt()
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": raw}],
                response_format=EventDetailsList,  # ALWAYS expect a list
            )
            extracted_events = completion.choices[0].message.parsed.events
        except Exception as e:
            st.error(f"LLM extraction failed for {url}: {e}")
            extracted_events = [EventDetails(
                title="", start_date=None, start_time=None, end_date=None,
                end_time=None, category="Tech", price="", location=None,
                description="", source_url=url,
            )]
        
        # Add source URL and append
        for details in extracted_events:
            if url and not details.source_url:
                details.source_url = url
            details_list.append(details)
            raw_texts.append(raw)
            prompts.append(system_prompt)

    # 2. Process Free Text block (can contain multiple events)
    if free_text_block:
        system_prompt = build_prompt()
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": free_text_block}],
                response_format=EventDetailsList, # Use the list format!
            )
            extracted_events = completion.choices[0].message.parsed.events
            
            for details in extracted_events:
                details_list.append(details)
                raw_texts.append(free_text_block)
                prompts.append(system_prompt)
                
        except Exception as e:
            st.error(f"LLM multi-event extraction failed: {e}")

    return details_list, raw_texts, prompts
