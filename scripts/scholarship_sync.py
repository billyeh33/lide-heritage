"""立德家傳 獎學金同步：每天讀公開的獎學金清單，存成 scholarships.json。

資料來源（都不用登入，只讀）：
  1. 清華助學系統 https://meo110.wwlc.nthu.edu.tw/ 收件中的公告（API）
  2. 教育部圓夢助學網 民間團體、政府機關獎助學金（只收大專院校或研究所能申請的）
陽明交大的校外獎學金系統只開放校內網路，抓不到。
"""
import html, json, re, time, urllib.request
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


POOR = re.compile(r"低收|中低|清寒|弱勢|家境|貧|急難|特殊境遇|不利")
AREA = re.compile(r"設籍|籍貫|縣|市民|同鄉|鄉親|校友")


def flags(ident, area, levels, desc, amount_max, title=""):
    """篩選用標記：open 不限身分、poor 低收清寒、grad 研究生可申請、area 限縣市或特定身分。"""
    ident, area, levels, desc = ident or "", area or "", levels or "", desc or ""
    f = []
    if POOR.search(title + " " + ident + " " + desc[:200]):
        f.append("poor")
    if (area and area not in ("不拘", "不限")) or AREA.search(ident + " " + title):
        f.append("area")
    if not levels or re.search(r"研究所|碩|博", levels):
        f.append("grad")
    if not ident.strip(" 不拘不限一般生本國生、") and "area" not in f and "poor" not in f:
        f.append("open")
    return {"flags": f, "amountMax": amount_max}


def nthu():
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
        hi = int(float(b.get("bonus_upper_bound") or 0))
        meta = flags("、".join(ids), "", "、".join(map(str, grades)), desc, hi, name)
        out.append({
            "id": "sch" + a["id"], "cat": "perk", "title": name, "grade": "不限",
            "tags": ["獎學金", kind] if kind else ["獎學金"], "summary": summary, "tips": tips,
            "source": f"清華助學系統 公告 {a['id']}", "date": a.get("announce_start_date", ""),
            "deadline": a.get("receive_end_date") or None, "link": SITE + "/", "linkLabel": "到清華助學系統申請",
            "extraLinks": att, **meta,
        })
    return out


MOE = "https://www.edu.tw/helpdreams/"
MOE_LISTS = [("2BBF7170197CE7D3", "0A01A72AAB9E5CD4", "民間"), ("11EFF33070D6DF4B", "931FF851D2FB2128", "政府")]


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (LideHeritageScholarship)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return html.unescape(r.read().decode("utf-8", "replace"))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3)


def roc(d):
    m = re.match(r"(\d{2,3})[-/](\d{1,2})[-/](\d{1,2})", d or "")
    return f"{int(m[1]) + 1911}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None


def moe():
    out = []
    for n, sms, kind in MOE_LISTS:
        page = fetch(f"{MOE}Grants.aspx?n={n}&sms={sms}")
        rows = re.findall(r'href="(Grants_Content\.aspx[^"]+)">(.*?)</a>\s*</td><td[^>]*>(.*?)</td><td[^>]*>(.*?)</td>', page, flags=re.S)
        for href, name, org, end in rows:
            name, org = clean(re.sub(r"<[^>]+>", "", name)), clean(re.sub(r"<[^>]+>", "", org))
            try:
                d = fetch(MOE + href)
            except Exception as e:
                print("略過", name, e)
                continue
            text = re.sub(r"<script.*?</script>", "", d, flags=re.S)
            cells = [clean(x) for x in re.split(r"<[^>]+>", text)]
            cells = [c for c in cells if c]
            def field(label):
                try:
                    i = cells.index(label)
                except ValueError:
                    return ""
                return cells[i + 1] if i + 1 < len(cells) else ""
            level = field("學 制")
            if level and not any(k in level for k in ("大專", "大學", "研究所")):
                continue
            ident, area = field("獎助身分"), field("戶籍地限制")
            nums = [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", re.sub(r"預計總名額.*", "", field("獎助內容")))]
            amt = money(nums[0], nums[-1]) if nums else ""
            meta = flags(ident, area, level, "", nums[-1] if nums else 0, name)
            period = field("申請期間")
            how = field("申請方式")
            url = field("說明網址")
            summary = "　".join(x for x in [f"金額 {amt}" if amt else "", f"限 {ident}" if ident and ident != "不拘" else "",
                                             f"戶籍 {area}" if area and area not in ("不拘", "不限") else ""] if x)
            out.append({
                "id": "moe" + re.sub(r"\W", "", href.split("s=")[-1])[:20], "cat": "perk", "title": name, "grade": "不限",
                "tags": ["獎學金", kind], "summary": (summary + "。" if summary else "") + f"提供單位：{org}。",
                "tips": [x for x in [f"申請期間 {period}" if period else "", how[:60], f"學制：{level}" if level else ""] if x],
                "source": "教育部圓夢助學網", "date": datetime.now(TW).strftime("%Y-%m-%d"),
                "deadline": roc(clean(end)), "link": MOE + href, "linkLabel": "看完整辦法",
                "extraLinks": [url] if url.startswith("http") else [], **meta,
            })
            time.sleep(0.5)
    return out


def grams(name):
    name = re.sub(r"\d{3}\s*(學)?年(度)?|第[^屆]*屆|[（(].*?[)）]|[「」【】\s、，]|獎助學金|獎學金|助學金|財團法人|社團法人", "", name)
    return {name[i:i + 4] for i in range(len(name) - 3)}


def main():
    items = []
    for f in (nthu, moe):
        try:
            got = f()
            print(f.__name__, len(got), "筆")
            items += got
        except Exception as e:
            print(f.__name__, "抓取失敗：", e)
    # 清大的全部保留，教育部的如果跟清大某筆名稱有連續 4 個字相同就略過
    nthu_grams = set().union(*[grams(e["title"]) for e in items if e["id"].startswith("sch")] or [set()])
    out = [e for e in items if e["id"].startswith("sch") or not (grams(e["title"]) & nthu_grams)]
    if not out:
        print("兩個來源都沒抓到，保留舊資料")
        return
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
