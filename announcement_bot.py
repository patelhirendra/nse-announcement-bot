import asyncio
import json
import os
import re
import httpx

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "937555558")
STATE_FILE = "seen_seqs.json"
MAX_SEEN_CACHE = 1000  # Keep memory footprint tiny

POLL_INTERVAL = 30  # Seconds between checks
CHECK_LIMIT = 50

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Fast Keyword Mapping
KEYWORDS = {
    r"\bdividend\b": "💰 DIVIDEND ALERT",
    r"\bcontract\b": "📜 CONTRACT ALERT",
    r"\bbonus\b": "🎁 BONUS ALERT",
    r"\bsplit\b": "🔀 STOCK SPLIT ALERT",
    r"\bbuyback\b": "🛒 BUYBACK ALERT",
    r"\brights\b": "📢 RIGHTS ISSUE ALERT",
    r"\bresult\b": "📊 RESULT ALERT",
    r"\bboard meeting\b": "📅 BOARD MEETING ALERT",
    r"\b(merger|acquisition)\b": "🤝 MERGER / ACQUISITION ALERT",
    r"\bfund raising\b": "💸 FUND RAISING ALERT",
}

# Pre-compile individual patterns into a tuple for blazingly fast checks
COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), label) 
    for pattern, label in KEYWORDS.items()
]

def detect_alert_type(text: str) -> str | None:
    """Check pre-compiled regexes against text."""
    for pattern, label in COMPILED_PATTERNS:
        if pattern.search(text):
            return label
    return None

# ---------------- STATE MANAGEMENT ----------------

def load_seen_ids() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_ids(seen_set: set):
    # Truncate old sequence IDs to prevent infinite file growth
    trimmed = list(seen_set)[-MAX_SEEN_CACHE:]
    with open(STATE_FILE, "w") as f:
        json.dump(trimmed, f)

# ---------------- TELEGRAM ----------------

async def send_telegram(client: httpx.AsyncClient, message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        await client.post(url, json=payload, timeout=10.0)
    except Exception as e:
        print(f"Telegram error: {e}")

# ---------------- NSE HANDSHAKE ----------------

async def fetch_nse_announcements(client: httpx.AsyncClient) -> list:
    url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
    
    for attempt in range(3):
        try:
            response = await client.get(url, headers=NSE_HEADERS, timeout=10.0)
            if response.status_code == 200:
                return response.json()
            
            # Refresh session on error
            await client.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10.0)
        except Exception as e:
            print(f"NSE Fetch Attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2)
            
    return []

def detect_alert_type(text: str) -> str | None:
    text_lower = text.lower()
    for pattern, label in KEYWORDS.items():
        if re.search(pattern, text_lower):
            return label
    return None

# ---------------- MAIN LOOP ----------------

async def main():
    seen_seqs = load_seen_ids()

    async with httpx.AsyncClient(http2=True) as client:
        # Initial NSE handshake to capture cookies
        try:
            await client.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10.0)
        except Exception as e:
            print(f"Initial handshake warning: {e}")

        await send_telegram(client, "✅ <b>NSE Announcement Bot Started</b>")

        while True:
            try:
                announcements = await fetch_nse_announcements(client)
                
                # Filter unseen
                new_announcements = [
                    ann for ann in announcements[:CHECK_LIMIT] 
                    if str(ann.get("seq_id")) not in seen_seqs
                ]

                # Process chronologically
                for ann in reversed(new_announcements):
                    seq = str(ann.get("seq_id"))
                    seen_seqs.add(seq)

                    company = ann.get("sm_name", "N/A")
                    symbol = ann.get("symbol", "N/A")
                    subject = ann.get("desc", "")
                    details = ann.get("attchmntText", "") or subject
                    broadcast = ann.get("an_dt", "N/A")
                    pdf = ann.get("attchmntFile", "")

                    alert = detect_alert_type(f"{subject} {details}")

                    if alert:
                        message = (
                            f"🚨 <b>{alert}</b> 🚨\n\n"
                            f"📢 <b>NSE Announcement</b>\n"
                            f"🏢 <b>Company:</b> {company}\n"
                            f"📊 <b>Symbol:</b> {symbol}\n\n"
                            f"📌 <b>Subject:</b>\n{subject}\n\n"
                            f"📝 <b>Details:</b>\n{details}\n\n"
                            f"⏰ <b>Broadcast:</b> {broadcast}\n"
                            f"📄 <a href='{pdf}'>Download Attachment</a>"
                        )
                        await send_telegram(client, message)
                        await asyncio.sleep(0.3)

                if new_announcements:
                    save_seen_ids(seen_seqs)

            except Exception as e:
                print(f"Main loop error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
