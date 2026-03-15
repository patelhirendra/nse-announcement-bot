import requests
import time
import sqlite3
import random

BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "937555558"

POLL_INTERVAL = 8
CHECK_LIMIT = 50

# ---------------- DATABASE ----------------

conn = sqlite3.connect("announcements.db")
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
"User-Agent":"Mozilla/5.0",
"Accept":"application/json",
"Referer":"https://www.nseindia.com/"
}

session.get("https://www.nseindia.com",headers=headers)

# ---------------- IMPORTANT KEYWORDS ----------------

important_keywords=[
"dividend",
"bonus",
"split",
"rights",
"buyback",
"results",
"board meeting",
"merger",
"acquisition",
"fund raising"
]

# ---------------- TELEGRAM ----------------

def send(msg):

    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url,data={
        "chat_id":CHAT_ID,
        "text":msg
    })

# ---------------- DATABASE HELPERS ----------------

def already_sent(seq):

    cursor.execute("SELECT seq_id FROM announcements WHERE seq_id=?",(seq,))
    return cursor.fetchone()

def store(seq):

    cursor.execute("INSERT INTO announcements VALUES(?)",(seq,))
    conn.commit()

# ---------------- SAFE REQUEST ----------------

def safe_request(url):

    retries=5

    for i in range(retries):

        try:

            r=session.get(url,headers=headers,timeout=10)

            if r.status_code==200:
                return r.json()

        except Exception as e:

            print("Request failed:",e)

        try:
            session.get("https://www.nseindia.com",headers=headers)
        except:
            pass

        time.sleep(3+i)

    return None

# ---------------- PRICE FETCH ----------------

def get_price(symbol):

    try:

        url=f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

        data=safe_request(url)

        if data:

            price=data["priceInfo"]["lastPrice"]
            change=data["priceInfo"]["pChange"]

            change=round(float(change),2)

            return price,change

    except:
        pass

    return "NA","NA"

# ---------------- MAIN LOOP ----------------

while True:

    try:

        url="https://www.nseindia.com/api/corporate-announcements?index=equities"

        announcements=safe_request(url)

        if announcements is None:
            time.sleep(10)
            continue

        new_items=[]

        for ann in announcements[:CHECK_LIMIT]:

            seq=ann["seq_id"]

            if not already_sent(seq):
                new_items.append(ann)

        new_items.reverse()

        for ann in new_items:

            seq=ann["seq_id"]

            company=ann["sm_name"]
            symbol=ann["symbol"]
            details=ann["desc"]
            broadcast=ann["an_dt"]
            pdf=ann["attchmntFile"]

            price,change=get_price(symbol)

            important=any(k in details.lower() for k in important_keywords)

            label=""
            if important:
                label="🚨 IMPORTANT ANNOUNCEMENT 🚨\n"

            message=f"""
{label}📢 NSE Corporate Announcement

🏢 Company: {company}
📊 Symbol: {symbol}

💰 Price: ₹{price}
📈 Change: {change}%

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

        print("Main loop error:",e)

    time.sleep(POLL_INTERVAL + random.uniform(1,3))
