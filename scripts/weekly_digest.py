"""每週一早上把「這兩週的立德活動、報名截止、快截止的獎學金」貼到 DC 頻道。

用 Discord 頻道的 Webhook 發文（不用給 Bot 發文權限）。
需要 GitHub Secret：DISCORD_WEBHOOK_URL。沒設定就不發，不會失敗。
"""
import json, os, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://billyeh33.github.io/lide-heritage/"
HOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
TW = timezone(timedelta(hours=8))
W = "一二三四五六日"


def load(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def fmt(d):
    dt = date.fromisoformat(d)
    return f"{dt.month}/{dt.day}（{W[dt.weekday()]}）"


def main():
    today = datetime.now(TW).date()
    end = today + timedelta(days=14)
    rows = []
    for e in load("dc.json").get("entries", []):
        nxt = next((d for d in e.get("events", []) if today <= date.fromisoformat(d) <= end), None)
        if nxt:
            rows.append((nxt, f"📅 {fmt(nxt)} {e['title'][:40]}"))
        if e.get("deadline") and today <= date.fromisoformat(e["deadline"]) <= end:
            rows.append((e["deadline"], f"⏰ {fmt(e['deadline'])} 報名截止：{e['title'][:36]}"))
    rows.sort()
    sch = sorted([(e["deadline"], e) for e in load("scholarships.json").get("entries", [])
                  if e.get("deadline") and today <= date.fromisoformat(e["deadline"]) <= today + timedelta(days=10)], key=lambda x: x[0])
    cal = next((e for e in load("calendar.json").get("events", []) if date.fromisoformat(e["date"]) >= today), None)

    parts = [f"**📚 立德家傳 每週提醒｜{today.month}/{today.day}**"]
    if cal:
        n = (date.fromisoformat(cal["date"]) - today).days
        parts.append(f"{'🏖️ ' + cal['label'] if cal['kind'] == 'break' else '🎒 開學'}倒數 **{n}** 天（{fmt(cal['date'])}）")
    if rows:
        parts.append("**這兩週的立德活動**\n" + "\n".join(r for _, r in rows[:10]))
    if sch:
        parts.append("**10 天內截止的獎學金**\n" + "\n".join(f"💰 {fmt(d)} {e['title'][:34]}" for d, e in sch[:8]))
    parts.append(f"完整清單和更多獎學金 👉 {SITE}")
    msg = "\n\n".join(parts)[:1990]

    if not HOOK:
        print("沒有設定 DISCORD_WEBHOOK_URL，這次只預覽不發文：\n" + msg)
        return
    req = urllib.request.Request(HOOK, data=json.dumps({"content": msg, "allowed_mentions": {"parse": []}}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "LideHeritageDigest (1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("已發到 DC，狀態", r.status)


if __name__ == "__main__":
    main()
