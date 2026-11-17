import argparse
import time

from firebase_admin import firestore
from app import classifier, drafter, retriever
from app.retry import DELAY_BETWEEN, call_with_retry
# from google.genai import errors

from app.firebase_repo import fetch_pending, get_db, save_ai_draft

# MAX_RETRY = 3
# DELAY_BETWEEN = 10
# RETRY_CODES = {429, 503}

# def call_with_retry(func, *args, **kwargs):
#     """429(한도 초과)면 기다렸다가 다시 시도, 다른 에러는 그대로 올림"""

#     for attempt in range(1, MAX_RETRY +1):
#         try:
#             return func(*args, **kwargs)
#         except errors.APIError as e:
#             if e.code not in RETRY_CODES or attempt == MAX_RETRY:
#                 raise
#             wait = 20 * attempt
#             print(f" 한도 초과, {wait}초 후 재시도 ({attempt}/{MAX_RETRY})")
#             time.sleep(wait)


def run(limit: int, write:bool) -> None:
    print("연결된 프로젝트:", get_db().project)
    print("모드:", "저장" if write else "확인만(저장 안함)")

    inquiries = fetch_pending(limit) 
    ok,fail =0, 0

    for inq in inquiries:
        content = inq.get("content", "")
        try:
            c = call_with_retry(classifier.classify,inq.get("category","기타"),content)
            sources = call_with_retry(retriever.search, content) if c.needs_policy else []
            d = call_with_retry(drafter.draft, content, c, sources=sources)
        except Exception as e:
            print(f"[실패] {inq['id']}: {str(e)[:100]}")
            fail += 1
            continue
        
        fields = {
            "aiCategory": c.category,
            "aiUrgency": c.urgency,
            "aiSubType": c.sub_type,
            "aiMissingInfo": c.missing_info,
            "aiConfidence": c.confidence,
            "aiDraft": d.draft_reply,
            "aiPromptVersion": f"{classifier.PROMPT_PATH.stem}+{drafter.PROMPT_PATH.stem}",
            "aiModel": classifier.MODEL,
            "aiCreatedAt": firestore.SERVER_TIMESTAMP,
            "aiNeedsPolicy": c.needs_policy,
            "aiSource": [
                {"source": s["source"], "title": s["title"], "score": round(s["score"],3)}
                for s in sources
            ]
        }

        print(f"\n[{c.category}/{c.urgency}/{c.sub_type}] {content[:40]}")
        print(" 초안:", d.draft_reply[:80])

        for s in sources:
            print(f"    근거: {s['source']} / {s['title']}")

        if write:
            save_ai_draft(inq["id"], fields)
            ok += 1

    print(f"\n총 {len(inquiries)}건 중 {ok}건 저장, {fail}건 실패")     


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--write", action="store_true", help="붙이면 Firestore에 저장")
    args = parser.parse_args()
    run(args.limit, args.write)