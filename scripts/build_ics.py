"""產生可訂閱的行事曆 lide.ics：立德 DC 活動與報名截止、獎學金截止、寒暑假與開學。

訂閱網址：webcal://billyeh33.github.io/lide-heritage/lide.ics
手機或 Google 行事曆訂閱後會自動更新（Google 大約每天抓一次）。
"""
import json, re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://billyeh33.github.io/lide-heritage/"
TW = timezone(timedelta(hours=8))


def load(name):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def esc(t):
    return re.sub(r"([,;\\])", r"\\\1", (t or "").replace("\n", " "))[:300]


def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b" " + b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def main():
    today = datetime.now(TW).date()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev = []

    def add(uid, d, title, desc, url):
        dt = date.fromisoformat(d)
        if dt < today - timedelta(days=30):
            return
        ev.append([
            "BEGIN:VEVENT", f"UID:{uid}@lide-heritage", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{dt:%Y%m%d}", f"DTEND;VALUE=DATE:{dt + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(desc)}", f"URL:{url}", "TRANSP:TRANSPARENT", "END:VEVENT"])

    for e in load("dc.json").get("entries", []):
        for d in e.get("events", [])[:3]:
            add(f"{e['id']}-ev-{d}", d, f"【立德】{e['title']}", e.get("summary", ""), e.get("link", SITE))
        if e.get("deadline"):
            add(f"{e['id']}-due", e["deadline"], f"【立德截止】{e['title']}", e.get("summary", ""), e.get("link", SITE))
    for e in load("scholarships.json").get("entries", []):
        if e.get("deadline"):
            add(f"{e['id']}-due", e["deadline"], f"【獎學金截止】{e['title']}", e.get("summary", ""), e.get("link", SITE))
    for e in load("calendar.json").get("events", []):
        name = f"{e['label']}開始" if e["kind"] == "break" else "開學上課"
        add(f"cal-{e['date']}-{e['kind']}", e["date"], f"【清大】{name}", e.get("title", ""), SITE)

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//lide-heritage//zh-TW", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:立德家傳", "X-WR-TIMEZONE:Asia/Taipei",
             "X-WR-CALDESC:立德 DC 活動、報名截止、獎學金截止與清大寒暑假", "REFRESH-INTERVAL;VALUE=DURATION:PT12H"]
    for block in ev:
        lines += block
    lines.append("END:VCALENDAR")
    body = "\r\n".join(fold(l) for l in lines) + "\r\n"
    out = ROOT / "lide.ics"
    old = out.read_text(encoding="utf-8") if out.exists() else ""
    if re.sub(r"DTSTAMP:\S+", "", old) == re.sub(r"DTSTAMP:\S+", "", body):
        print("行事曆檔沒有變動")
        return
    out.write_text(body, encoding="utf-8", newline="")
    print(f"lide.ics 更新：{len(ev)} 個事件")


if __name__ == "__main__":
    main()
