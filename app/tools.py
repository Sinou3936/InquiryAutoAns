"""에이전트가 쓰는 도구 모음. 전부 읽기 전용"""
import json
import sys
from collections import defaultdict

from app import firebase_repo, retriever
from datetime import timedelta, timezone

PREVIEW_LEN = 30

KST = timezone(timedelta(hours=9))

def _fmt_time(ts) -> str | None:
    return ts.astimezone(KST).strftime("%Y-%m-%d %H:%M") if ts else None

def _post_state(p:dict) -> str:
    if not p.get("isDeleted"):
        return "공개"
    return "본인 삭제" if p.get("deletedAt") else "숨김(신고 누적 또는 관리자 조치)"

def get_user_posts(uid:str) -> dict:
    """문의한 사용자의 최근 글 10개와 각 글의 상태"""
    posts = firebase_repo.fetch_user_posts(uid)
    return {
        "count": len(posts),
        "posts": [
            {
                "post_id": p["id"],
                "preview": (p.get("content") or "")[:PREVIEW_LEN],
                "state": _post_state(p),
                "created_at" : _fmt_time(p.get("createdAt"))
            }
            for p in posts
        ]
    }

def get_reports(uid:str) -> dict:
    """문의한 사용자의 글에 접수된 신고 건수와 사유"""
    posts = firebase_repo.fetch_user_posts(uid)
    by_id = {p["id"]: p for p in posts}
    reports = firebase_repo.fetch_reports_for_posts(list(by_id))

    counts = defaultdict(int)
    reasons = defaultdict(set)

    for r in reports:
        counts[r["targetId"]] += 1
        if r.get("reason"):
            reasons[r["targetId"]].add(r["reason"])

    return {
        "reported_posts": [
            {
                "post_id": pid,
                "preview": (by_id[pid].get("content") or "")[:PREVIEW_LEN],
                "state": _post_state(by_id[pid]),
                "report_count": n,
                "reasons": sorted(reasons[pid])[:3]
            }
            for pid, n in counts.items()
        ]
    }

def get_user_profile(uid:str) -> dict:
    """문의한 사용자의 레벨과 유저네임 변경권"""
    u = firebase_repo.fetch_user(uid)
    return{
        "trust_level": u.get("trustLevel", 0),
        "username_changes_left": u.get("usernameChangesLeft",0)
    }

def search_policy(query:str) -> dict:
    """운영 정책·FAQ에서 관련 문단 검색"""
    hits = retriever.search(query, k=3)
    return{
        "results":[
            {"source": h["source"], "title": h["title"], "text": h["text"]}
            for h in hits
        ]
    }

UID_TOOLS = {
    "get_user_posts": get_user_posts,
    "get_reports": get_reports,
    "get_user_profile": get_user_profile
}

def run_tool(name:str, uid:str, args:dict) -> dict:
    """에이전트가 고른 도구를 실행, 실패해도 예외 대신 에러 dict를 돌려줌"""
    try:
        if name in UID_TOOLS:
            return UID_TOOLS[name](uid)
        if name =="search_policy":
            query = str(args.get("query","")).strip()
            if not query:
                return {"error": "query가 비어 있음"}
            return search_policy(query)
        return {"error": f"없는 도구: {name}"}
    except Exception as e:
        return {"error": f"{name} 실행 실패: {str(e)[:100]}"}


if __name__ == "__main__":
    uid = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else "게시글이 사라졌어요"


    for name, reuslt in [
        ("get_user_posts", get_user_posts(uid)),
        ("get_reports",get_reports(uid)),
        ("get_user_profile",get_user_profile(uid)),
        ("search_policy",search_policy(query))
    ]:
        print(f"\n========== {name} ==========")
        print(json.dumps(reuslt, ensure_ascii=False, indent=2))