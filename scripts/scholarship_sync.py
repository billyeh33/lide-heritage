"""立德家傳 獎學金同步：每天讀清華助學系統公開的「收件中」獎學金，存成 scholarships.json。

資料來源：https://meo110.wwlc.nthu.edu.tw/ 首頁的公開 API（不用登入，只讀）。
"""
import json, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SITE = "https://meo110.wwlc.nthu.edu.tw"
API = SITE + "/api/v1/announcement/list?in_announce_period=true"
OUT = Path(__file__).resolve().parent.parent / "scholarships.json"
TW = timezone(timedelta(hours=8))


def money(lo, hi):
    lo, hi = int(float(lo or 0)), int(float(hi or 0))
    if not hi:
        return ""
    return f"{hi} 元" if lo in (0, hi) and lo == hi else (f"最高 {hi} 元" if lo == 0 else f"{lo}–{hi} 元")


def clean(text):
    text = re.sub(r"[●■◆★※]|-{3,}", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def main():
    req = urllib.request.Request(API, headers={"User-Agent": "LideHeritageScholarship (github-actions, 1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.loads(r.read())["result"]["data"]
    out = []
    for a in items:
        b, q = a.get("basic_info", {}), a.get("qualification_info", {})
        name = (b.get("name") or "").strip()
        if not name:
            continue
        amt = money(b.get("bonus_lower_bound"), b.get("bonus_upper_bound"))
        ids = [x for x in q.get("identities") or [] if x]
        grades = q.get("grades") or []
        how = "線上申請" if b.get("is_online_apply") else "系統登記後繳紙本"
        kind = {1: "校外", 2: "校內"}.get(b.get("type"), "")
        desc = clean(b.get("description"))
        summary = "　".join(x for x in [f"金額 {amt}" if amt else "", f"限 {'、'.join(ids)}" if ids else ""] if x)
        summary = (summary + "。" if summary else "") + desc[:140] + ("…" if len(desc) > 140 else "")
        tips = [f"收件 {a.get('receive_start_date','')} 到 {a.get('receive_end_date','')}", how]
        if grades:
            tips.append("年級：" + "、".join(map(str, grades)))
        tips.append(f"承辦 {a.get('specialist','')} 分機 {a.get('ext','')}".strip())
        att = [x["src"] for x in b.get("attachments", []) if x.get("src", "").lower().endswith(".pdf")][:2]
        out.append({
            "id": "sch" + a["id"], "cat": "perk", "title": name, "grade": "不限",
            "tags": ["獎學金", kind] if kind else ["獎學金"], "summary": summary, "tips": tips,
            "source": f"清華助學系統 公告 {a['id']}", "date": a.get("announce_start_date", ""),
            "deadline": a.get("receive_end_date") or None, "link": SITE + "/", "linkLabel": "到清華助學系統申請",
            "extraLinks": att,
        })
    out.sort(key=lambda x: x["deadline"] or "9999")
    data = {"updated": datetime.now(TW).strftime("%Y-%m-%d %H:%M"), "entries": out}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("entries") == out:
        print("獎學金沒有變動")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"scholarships.json 更新：{len(out)} 筆")


if __name__ == "__main__":
    main()
