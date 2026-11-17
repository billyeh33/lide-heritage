"""立德家傳 DC 同步：用官方 Bot 讀白名單頻道，整理成 dc.json 給網站讀。

只讀不發文。不存發文者姓名、頭像、附件檔，只留標題、前 160 字、連結和 DC 原文網址。
需要環境變數（GitHub 上放在 Settings → Secrets and variables → Actions）：
  DISCORD_BOT_TOKEN   Bot token
  DISCORD_GUILD_ID    立德伺服器 ID
  DISCORD_CHANNEL_IDS 要同步的頻道 ID，用逗號分隔（論壇頻道或文字頻道）
沒有設定時直接結束，不會失敗。
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://discord.com/api/v10"
OUT = Path(__file__).resolve().parent.parent / "dc.json"
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
GUILD = os.environ.get("DISCORD_GUILD_ID", "").strip()
CHANNELS = [c.strip() for c in os.environ.get("DISCORD_CHANNEL_IDS", "").split(",") if c.strip()]
KEEP_DAYS = 400
# 論壇貼文只收有這些標籤的（聊天、家族、便當會這類不收）
TAG_ALLOW = [t.strip() for t in os.environ.get("DISCORD_TAG_ALLOW", "活動資訊,學術資源,職涯機會,福利與贈品").split(",") if t.strip()]
DATE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")
CUT = re.compile(r"截止|deadline|due", re.I)
STRONG = re.compile(r"報名", re.I)
WEAK = re.compile(r"前|至|到")
URL = re.compile(r"https?://[^\s<>)]+")
MENTION = re.compile(r"<[@#][!&]?\d+>|<a?:\w+:\d+>")

# 論壇標籤或頻道名 → 網站分類
CAT_RULES = [
    ("perk", ["福利", "贈品", "獎學金", "好康", "優惠", "免費"]),
    ("compete", ["競賽", "比賽", "黑客松", "職涯", "實習", "徵才", "研究"]),
    ("course", ["學術", "課程", "考古", "修課", "學習", "講義"]),
    ("lead", ["活動", "講座", "營隊", "工作坊", "立德", "校園", "志工"]),
]


def get(path):
    for _ in range(6):
        req = urllib.request.Request(API + path, headers={"Authorization": "Bot " + TOKEN, "User-Agent": "LideHeritageSync (github-actions, 1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                time.sleep(float(json.loads(body).get("retry_after", 2)) + 0.5)
                continue
            if e.code == 401:
                sys.exit("Bot token 不對，請重新產生並更新 GitHub Secret")
            if e.code in (400, 403, 404):
                print(f"略過 {e.code}：{path} {body[:120]}")
                return None
            raise
    return None


def classify(words):
    text = " ".join(words)
    for cat, keys in CAT_RULES:
        if any(k in text for k in keys):
            return cat
    return "lead"


def clean(text):
    text = MENTION.sub("", text or "")
    text = re.sub(r"[*_~`>|]{1,3}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def find_deadline(text, posted):
    """找截止日：先找「截止、報名、deadline」後面最近的 M/D，沒有再找含「前、至、到」句子裡最晚的 M/D。"""
    try:
        base = datetime.fromisoformat(posted.replace("Z", "+00:00")).date()
    except ValueError:
        return None

    def to_date(m, d):
        m, d = int(m), int(d)
        for y in (base.year, base.year + 1):
            try:
                dt = datetime(y, m, d).date()
            except ValueError:
                return None
            if base <= dt <= base + timedelta(days=300):
                return dt
        return None

    text = text or ""
    for pat in (CUT, STRONG):
        for k in pat.finditer(text):
            for m in DATE.finditer(text[k.end():k.end() + 30]):
                dt = to_date(*m.groups())
                if dt:
                    return dt.isoformat()
    best = None
    for sent in re.split(r"[。\n！!？?]", text):
        if WEAK.search(sent):
            for m, d in DATE.findall(sent):
                dt = to_date(m, d)
                if dt:
                    best = max(best, dt) if best else dt
    return best.isoformat() if best else None


def find_events(text, posted):
    """活動當天的日期：內文所有 M/D（發文後 300 天內），去掉只出現在「截止、報名」後面的那個。"""
    try:
        base = datetime.fromisoformat(posted.replace("Z", "+00:00")).date()
    except ValueError:
        return []
    found = set()
    for m in DATE.finditer(text or ""):
        before = (text or "")[max(0, m.start() - 8):m.start()]
        if CUT.search(before):
            continue
        mo, d = int(m[1]), int(m[2])
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            continue
        for y in (base.year, base.year + 1):
            try:
                dt = datetime(y, mo, d).date()
            except ValueError:
                break
            if base <= dt <= base + timedelta(days=300):
                found.add(dt.isoformat())
                break
    return sorted(found)[:6]


def entry(kind, cid, mid, title, content, tags, chname, when, url):
    links = sorted(set(URL.findall(content or "")))[:5]
    body = clean(URL.sub("", content or ""))
    due = find_deadline((title or "") + "\n" + (content or ""), when)
    e = {
        "id": f"dc{mid}", "cat": classify(tags + [chname, title]), "title": clean(title)[:60] or "（沒有標題）",
        "grade": "不限", "tags": ["DC", *tags[:2]], "summary": body[:160] + ("…" if len(body) > 160 else ""),
        "tips": [], "source": f"立德 DC #{chname}", "date": when[:10],
        "link": f"https://discord.com/channels/{GUILD}/{cid}/{mid}", "linkLabel": "到 DC 看原文",
        "extraLinks": links, "kind": kind,
    }
    if due:
        e["deadline"] = due
    ev = [x for x in find_events((title or "") + "\n" + (content or ""), when) if x != due]
    if ev:
        e["events"] = ev
    return e


def main():
    if not (TOKEN and GUILD and CHANNELS):
        print("沒有設定 DISCORD_BOT_TOKEN、DISCORD_GUILD_ID 或 DISCORD_CHANNEL_IDS，這次跳過")
        return
    chans = {c["id"]: c for c in (get(f"/guilds/{GUILD}/channels") or [])}
    active = (get(f"/guilds/{GUILD}/threads/active") or {}).get("threads", [])
    since = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    out = []
    for cid in CHANNELS:
        c = chans.get(cid)
        if not c:
            print(f"頻道 {cid} 不在伺服器裡或 Bot 看不到，跳過")
            continue
        name = c["name"]
        if c["type"] in (15, 16):  # 論壇、媒體頻道：一篇貼文一筆
            tagname = {t["id"]: t["name"] for t in c.get("available_tags", [])}
            threads = {t["id"]: t for t in active if t.get("parent_id") == cid}
            before = None
            while True:
                r = get(f"/channels/{cid}/threads/archived/public?limit=100" + (f"&before={urllib.parse.quote(before)}" if before else ""))
                if not r or not r.get("threads"):
                    break
                for t in r["threads"]:
                    threads[t["id"]] = t
                if not r.get("has_more"):
                    break
                before = r["threads"][-1]["thread_metadata"]["archive_timestamp"]
            for t in threads.values():
                created = t.get("thread_metadata", {}).get("create_timestamp") or ""
                if created and datetime.fromisoformat(created.replace("Z", "+00:00")) < since:
                    continue
                first = get(f"/channels/{t['id']}/messages/{t['id']}") or {}
                tags = [tagname.get(x, "") for x in t.get("applied_tags", []) if tagname.get(x)]
                if TAG_ALLOW and not any(tag in TAG_ALLOW for tag in tags):
                    continue
                out.append(entry("post", t["id"], t["id"], t["name"], first.get("content", ""), tags, name, created or first.get("timestamp", ""), None))
        else:  # 文字、公告頻道：只收有連結的訊息
            for m in get(f"/channels/{cid}/messages?limit=100") or []:
                if not URL.search(m.get("content", "")):
                    continue
                if datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) < since:
                    continue
                first_line = clean(URL.sub("", m["content"])).split(" ")[0][:40]
                out.append(entry("msg", cid, m["id"], first_line, m["content"], [], name, m["timestamp"], None))
    out.sort(key=lambda x: x["date"], reverse=True)
    out = out[:300]
    data = {"updated": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"), "entries": out}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("entries") == out:
        print("DC 沒有新內容")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dc.json 更新：{len(out)} 筆")


if __name__ == "__main__":
    main()
