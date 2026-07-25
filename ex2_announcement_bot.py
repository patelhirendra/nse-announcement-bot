import os
import requests
import time
import random
import psycopg2

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "937555558"

POLL_INTERVAL = 60
CHECK_LIMIT = 25

# ---------------- DATABASE ----------------

conn = psycopg2.connect(
    host=os.getenv("PGHOST"),
    database=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    port=os.getenv("PGPORT")
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS announcements(
    seq_id TEXT PRIMARY KEY
)
""")
conn.commit()

# ---------------- SESSION ----------------

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/"
}

session.get("https://www.nseindia.com", headers=headers)

# ---------------- TELEGRAM ----------------

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ---------------- DATABASE HELPERS ----------------

def already_sent(seq):
    cursor.execute(
        "SELECT 1 FROM announcements WHERE seq_id=%s",
        (seq,)
    )
    return cursor.fetchone()

def store(seq):
    cursor.execute(
        "INSERT INTO announcements(seq_id) VALUES(%s)",
        (seq,)
    )
    conn.commit()

# ---------------- SAFE REQUEST ----------------

def fetch_json(url):

    for i in range(5):
        try:
            r = session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print("Request error:", e)

        # refresh cookies
        try:
            session.get("https://www.nseindia.com", headers=headers)
        except:
            pass

        time.sleep(2 + i)

    return None

# ---------------- ALERT TYPE ----------------

def get_alert_type(text):

    if "dividend" in text:
        return "💰 DIVIDEND ALERT"
    if "contract" in text:
        return "📜 CONTRACT ALERT"
    if "bonus" in text:
        return "🎁 BONUS ALERT"
    if "split" in text:
        return "🔀 STOCK SPLIT ALERT"
    if "buyback" in text:
        return "🛒 BUYBACK ALERT"
    if "rights" in text:
        return "📢 RIGHTS ISSUE ALERT"
    if "result" in text:
        return "📊 RESULT ALERT"
    if "board meeting" in text:
        return "📅 BOARD MEETING ALERT"
    if "merger" in text or "acquisition" in text:
        return "🤝 MERGER / ACQUISITION ALERT"
    if "fund raising" in text:
        return "💸 FUND RAISING ALERT"

    return None

# ---------------- START ----------------

send("✅ NSE Announcement Bot Started")

# ---------------- MAIN LOOP ----------------

while True:

    try:

        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"

        data = fetch_json(url)

        if not data:
            time.sleep(10)
            continue

        new_items = [
            ann for ann in data[:CHECK_LIMIT]
            if not already_sent(ann["seq_id"])
        ]

        for ann in reversed(new_items):

            seq = ann["seq_id"]

            company = ann["sm_name"]
            symbol = ann["symbol"]
            subject = ann.get("desc", "")
            details = ann.get("attchmntText", "") or subject
            broadcast = ann["an_dt"]
            pdf = ann["attchmntFile"]

            text = (subject + " " + details).lower()

            alert = get_alert_type(text)

            # ❌ Skip non-important
            if not alert:
                store(seq)
                continue

            message = f"""
🚨 {alert} 🚨

📢 NSE Corporate Announcement

🏢 Company: {company}
📊 Symbol: {symbol}

📌 Subject:
{subject}

📝 Details:
{details}

⏰ Broadcast Time:
{broadcast}

📄 Download PDF:
{pdf}
"""

            send(message)
            store(seq)

    except Exception as e:
        print("Main loop error:", e)

    time.sleep(POLL_INTERVAL + random.uniform(1, 3))
