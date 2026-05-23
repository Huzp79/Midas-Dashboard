import time, requests, os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID      = "44776511f85fbbd6e9ab314c7db09135"
GIST_FILE    = "midas_url.txt"
TG_TOKEN     = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID   = os.getenv("CHAT_ID")

def get_ngrok_url():
    resp = requests.get("http://localhost:4040/api/tunnels", timeout=5)
    tunnels = resp.json().get("tunnels", [])
    for t in tunnels:
        if t.get("proto") == "https":
            return t["public_url"]
    if tunnels:
        return tunnels[0]["public_url"]
    return None

def update_gist(url: str):
    if not GITHUB_TOKEN:
        print("[ngrok_notify] GITHUB_TOKEN not set — skipping Gist update")
        return
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    payload = {"files": {GIST_FILE: {"content": url}}}
    r = requests.patch(f"https://api.github.com/gists/{GIST_ID}", json=payload, headers=headers)
    if r.status_code == 200:
        print(f"[ngrok_notify] Gist updated: {url}")
    else:
        print(f"[ngrok_notify] Gist update failed ({r.status_code}): {r.text}")

def send_telegram(url: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("[ngrok_notify] Telegram credentials not set — skipping")
        return
    text = f"Midas is live\n{url}"
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT_ID, "text": text},
        timeout=10,
    )
    if r.status_code == 200:
        print(f"[ngrok_notify] Telegram sent")
    else:
        print(f"[ngrok_notify] Telegram failed ({r.status_code}): {r.text}")

def main():
    print("[ngrok_notify] Waiting 3 seconds for ngrok...")
    time.sleep(3)

    for attempt in range(1, 6):
        url = get_ngrok_url()
        if url:
            print(f"[ngrok_notify] ngrok URL: {url}")
            update_gist(url)
            send_telegram(url)
            return
        print(f"[ngrok_notify] Attempt {attempt}/5 — ngrok not ready, retrying in 2s...")
        time.sleep(2)

    print("[ngrok_notify] Could not get ngrok URL after 5 attempts.")

if __name__ == "__main__":
    main()
