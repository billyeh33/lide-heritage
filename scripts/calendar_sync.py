"""立德家傳 行事曆同步：讀清大教務處公開的 Google 行事曆，抓寒暑假開始與上課開始的日期，存成 calendar.json。

來源：教務處行事曆頁面（dgaa.site.nthu.edu.tw）公布的 nthu.acad@gmail.com 公開行事曆。
"""
import json, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ICS = "https://calendar.google.com/calendar/ical/nthu.acad%40gmail.com/public/basic.ics"
OUT = Path(__file__).resolve().parent.parent / "calendar.json"
TW = timezone(timedelta(hours=8))


def main():
    req = urllib.request.Request(ICS, headers={"User-Agent": "LideHeritageCalendar (github-actions, 1.0)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        text = r.read().decode("utf-8", "replace").replace("\r\n ", "").replace("\n ", "")
    today = datetime.now(TW).date()
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S):
        summary = re.search(r"SUMMARY[^:]*:(.*)", block)
        start = re.search(r"DTSTART[^:]*:(\d{8})", block)
        if not (summary and start):
            continue
        title = summary[1].strip().replace("\\,", ",")
        d = datetime.strptime(start[1], "%Y%m%d").date()
        if d < today - timedelta(days=200) or d > today + timedelta(days=400):
            continue
        if re.search(r"(寒假|暑假)開始", title):
            kind, label = "break", re.search(r"(寒假|暑假)", title)[1]
        elif "全校" in title and "上課開始" in title:
            kind, label = "classes", "開學"
        else:
            continue
        events.append({"date": d.isoformat(), "kind": kind, "label": label, "title": title.split(" ")[0]})
    events.sort(key=lambda e: e["date"])
    if not events:
        print("行事曆沒抓到寒暑假或開學日期，保留舊資料")
        return
    data = {"updated": datetime.now(TW).strftime("%Y-%m-%d %H:%M"), "source": "清華大學教務處行事曆", "events": events}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("events") == events:
        print("行事曆沒有變動")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"calendar.json 更新：{len(events)} 筆", [(e["date"], e["label"]) for e in events])


if __name__ == "__main__":
    main()
