"""立德家傳 作業佈告同步：把 repo 裡標了「佈告」的 Issue 整理成 bulletin.json。

只收 repo 擁有者、協作者發的 Issue（路人開的不會上網站）。
Issue 關閉就從網站下架。內文用 GitHub 轉好的 HTML（GitHub 會先過濾危險內容），檔案和圖片沿用 GitHub 的附件網址。
"""
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "billyeh33/lide-heritage")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "bulletin.json"
TW = timezone(timedelta(hours=8))
TRUSTED = {"OWNER", "COLLABORATOR", "MEMBER"}
GEN = {"F": "F", "G": "G", "H": "H"}


def api(path, accept="application/vnd.github+json", data=None):
    headers = {"Accept": accept, "User-Agent": "LideHeritageBulletin (1.0)", "X-GitHub-Api-Version": "2022-11-28"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request("https://api.github.com" + path, headers=headers,
                                 data=json.dumps(data).encode() if data else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
        return body if accept.endswith("raw") or accept == "text/html" else json.loads(body)


def sections(md):
    """把 Issue 表單的 markdown 拆成 {欄位: 內容}。"""
    out, cur = {}, None
    for line in (md or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            cur = m[1]
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def clean(v):
    return "" if not v or v.strip() == "_No response_" else v.strip()


def render(md):
    if not md:
        return ""
    return api("/markdown", accept="text/html", data={"text": md, "mode": "gfm", "context": REPO})


def main():
    issues, page = [], 1
    while True:
        batch = api(f"/repos/{REPO}/issues?labels=%E4%BD%88%E5%91%8A&state=open&per_page=100&page={page}")
        issues += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            break
        page += 1
    posts = []
    for i in issues:
        if i.get("author_association") not in TRUSTED:
            print(f"略過 #{i['number']}：{i['user']['login']} 不是管理者")
            continue
        f = sections(i.get("body") or "")
        gen_raw = clean(f.get("屆別", ""))
        gen = next((v for k, v in GEN.items() if gen_raw.startswith(("Foxtrot", "Gopher", "Hawk")[list(GEN).index(k)])), "ALL")
        kind = "作業" if clean(f.get("類型", "")) == "作業" else "公告"
        due = clean(f.get("截止時間", ""))
        m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", due)
        due_iso = f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else ""
        due_time = f"{int(m[4]):02d}:{m[5]}" if m and m[4] else ("23:59" if m else "")
        classroom = clean(f.get("Google Classroom 連結", ""))
        if classroom and not classroom.startswith("https://"):
            classroom = ""
        created = datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")).astimezone(TW)
        posts.append({
            "id": "bb" + str(i["number"]), "number": i["number"], "gen": gen, "kind": kind,
            "title": i["title"].strip(), "html": render(clean(f.get("內容", ""))),
            "due": due_iso, "dueTime": due_time, "classroom": classroom,
            "author": i["user"]["login"], "avatar": i["user"]["avatar_url"],
            "created": created.strftime("%Y-%m-%d %H:%M"), "edited": i["updated_at"] != i["created_at"],
            "url": i["html_url"],
        })
    posts.sort(key=lambda p: p["created"], reverse=True)
    data = {"updated": datetime.now(TW).strftime("%Y-%m-%d %H:%M"), "posts": posts}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("posts") == posts:
        print("佈告沒有變動")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"bulletin.json 更新：{len(posts)} 則")


if __name__ == "__main__":
    main()
