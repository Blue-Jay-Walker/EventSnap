# Test Cases for EventSnap & HomeSnap

This file contains scenarios to verify the event and apartment viewing extraction logic on a regular basis.

---

## 1. Event Mode (EventSnap 📸)

### Test Case 1.1: Single Event (Free-text)
* **Input:**
  ```text
  Photography workshop in Zurich on June 15, 6-9pm, price: 50 CHF, location: Photostudio Zurich.
  ```
* **Expected Output:**
  * **Title:** Photography workshop
  * **Start Date:** `[Current Year]-06-15`
  * **Start Time:** `18:00`
  * **End Time:** `21:00`
  * **Price:** `50 CHF`
  * **Location:** `Photostudio Zurich`
  * **Category:** `Social` or `Tech`

### Test Case 1.2: Multiple Events (Free-text)
* **Input:**
  ```text
  1. AI Meetup on July 10 at 19:00 at Technopark Zurich (Free).
  2. Board games night on July 12 from 18:30 to 22:00 at Oliver's flat.
  ```
* **Expected Output:**
  * **Event 1:**
    * **Title:** AI Meetup
    * **Start Date:** `[Current Year]-07-10`
    * **Start Time:** `19:00`
    * **Price:** `Free`
    * **Location:** `Technopark Zurich`
    * **Category:** `AI`
  * **Event 2:**
    * **Title:** Board games night
    * **Start Date:** `[Current Year]-07-12`
    * **Start Time:** `18:30`
    * **End Time:** `22:00`
    * **Location:** `Oliver's flat`
    * **Category:** `Games`

### Test Case 1.3: Event URL (Scraping)
* **Input:**
  ```text
  https://luma.html  (or any other public meetup event link)
  ```
* **Expected Output:**
  * App successfully scrapes the page content.
  * Correct title, date, time, price, and location are parsed.

---

## 2. Apartment Mode (HomeSnap 🏠)

### Test Case 2.1: Listing URL + Separate Viewing Schedule (Combined Input)
* **Input:**
  ```text
  https://flatfox.ch/en/flat/poststrasse-160-8957-spreitenbach/86086938/
  29 June at 18:00
  ```
* **Expected Output:**
  * **Title:** `Apartment Viewing: Poststrasse 160` (extracting street name and number from the URL or flat description)
  * **Start Date:** `[Current Year]-06-29`
  * **Start Time:** `18:00`
  * **Category:** `Apartment Viewing`
  * **Price:** `[Rent from Flatfox listing, e.g. 1500 CHF]`
  * **Location:** `Poststrasse 160, 8957 Spreitenbach`
  * **Source URL:** `https://flatfox.ch/en/flat/poststrasse-160-8957-spreitenbach/86086938/`

### Test Case 2.2: Apartment Viewing (Free-text Only)
* **Input:**
  ```text
  Apartment visit scheduled for July 5th at 17:30 at Main Street 12, 8001 Zurich. Rent is 2500 CHF/month.
  ```
* **Expected Output:**
  * **Title:** `Apartment Viewing: Main Street 12`
  * **Start Date:** `[Current Year]-07-05`
  * **Start Time:** `17:30`
  * **Category:** `Apartment Viewing`
  * **Price:** `2500 CHF/month`
  * **Location:** `Main Street 12, 8001 Zurich`

### Test Case 2.3: Relative Date/Time Resolution
* **Input:**
  ```text
  Tomorrow at 18:30
  https://flatfox.ch/en/flat/schilplinstrasse-10-5200-brugg-ag/86136246/
  ```
* **Expected Output (assuming today is 2026-06-30):**
  * **Title:** `Apartment Viewing: Schilplinstrasse 10`
  * **Start Date:** `2026-07-01` (resolves "Tomorrow" correctly relative to the current date)
  * **Start Time:** `18:30`
  * **Category:** `Apartment Viewing`
  * **Price:** `[Rent from Flatfox listing]`
  * **Location:** `Schilplinstrasse 10, 5200 Brugg AG`
  * **Source URL:** `https://flatfox.ch/en/flat/schilplinstrasse-10-5200-brugg-ag/86136246/`
