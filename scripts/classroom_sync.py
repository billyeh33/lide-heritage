"""立德家傳 作業同步：讀 Google Classroom 課程日曆的私人 iCal 網址，抓作業名稱和截止日，存成 assignments.json。

需要 GitHub Secret：CLASSROOM_ICS，一行一門課，格式「顯示名稱|iCal 網址」，例如
  創領六 Foxtrot|https://calendar.google.com/calendar/ical/.../private-xxxx/basic.ics
網址本身是私密的，只放在 Secret，不會出現在網站上。網站只顯示作業名稱和截止時間，不放作業內容。
沒有設定就跳過，不會失敗。
"""
import hashlib, json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assignments.json"
TW = timezone(timedelta(hours=8))
CONF = []
for _line in os.environ.get("CLASSROOM_ICS", "").splitlines():
    _line = _line.strip()
    if not _line:
        continue
    if "|" in _line and not _line.startswith("http"):
        CONF.append(_line.split("|", 1))
    elif _line.startswith("http"):
        CONF.append(["創領六", _line])  # 只貼網址時的預設名稱


def unfold(text):
    return text.replace("\r\n ", "").replace("\n ", "").replace("\r\n\t", "")


def field(block, name):
    m = re.search(rf"^{name}(;[^:]*)?:(.*)$", block, flags=re.M)
    return (m[1] or "", m[2].strip()) if m else ("", "")


def parse_dt(params, value):
    if re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(hour=23, minute=59, tzinfo=TW), False
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TW), True
    return datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=TW), True


def main():
    if not CONF:
        print("沒有設定 CLASSROOM_ICS，這次跳過")
        return
    now = datetime.now(TW)
    out = []
    for label, url in CONF:
        label, url = label.strip(), url.strip()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LideHeritageClassroom (github-actions, 1.0)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                text = unfold(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print(f"{label} 讀取失敗：{type(e).__name__} {str(e)[:80]}")
            continue
        n = 0
        for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S):
            p, v = field(block, "DTSTART")
            title = field(block, "SUMMARY")[1].replace("\\,", ",").replace("\\;", ";")
            if not (v and title):
                continue
            due, has_time = parse_dt(p, v)
            if due < now - timedelta(days=7) or due > now + timedelta(days=120):
                continue
            desc = field(block, "DESCRIPTION")[1].replace("\\n", " ")
            link = next(iter(re.findall(r"https://classroom\.google\.com/\S+", desc)), "https://classroom.google.com/")
            uid = hashlib.sha1((label + field(block, "UID")[1] + title).encode()).hexdigest()[:12]
            out.append({
                "id": "hw" + uid, "cat": "lead", "title": f"【{label}】{title}"[:80], "grade": "不限",
                "tags": ["作業", label], "summary": f"{label} 的作業，{due.month}/{due.day} {due:%H:%M} 截止。內容請到 Classroom 看。" if has_time else f"{label} 的作業，{due.month}/{due.day} 截止。內容請到 Classroom 看。",
                "tips": [], "source": f"Google Classroom {label}", "date": now.strftime("%Y-%m-%d"),
                "deadline": due.strftime("%Y-%m-%d"), "dueTime": due.strftime("%H:%M") if has_time else "",
                "link": link.rstrip(".,)"), "linkLabel": "到 Classroom 交作業",
            })
            n += 1
        print(f"{label}：{n} 項作業")
    out.sort(key=lambda e: (e["deadline"], e["dueTime"]))
    data = {"updated": now.strftime("%Y-%m-%d %H:%M"), "entries": out}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("entries") == out:
        print("作業沒有變動")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"assignments.json 更新：{len(out)} 項")


if __name__ == "__main__":
    main()
