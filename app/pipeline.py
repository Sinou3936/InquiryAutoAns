import argparse

from firebase_admin import firestore
from app import classifier, drafter

from app.firebase_repo import fetch_pending, get_db, save_ai_draft

def run(limit: int, write:bool) -> None:
    print("연결된 프로젝트:", get_db().project)
    print("모드:", "저장" if write else "확인만(저장 안함)")

    inquiries = fetch_pending(limit) 
    ok,fail =0, 0

    for inq in inquiries:
        content = inq.get("content", "")
        try:
            c = classifier.classify(inq.get("category","기타"),content)
            d = drafter.draft(content, c)
        except Exception as e:
            print(f"[실패] {inq['id']}: {e}")
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
            "aiCreatedAt": firestore.SERVER_TIMESTAMP
        }

        print(f"\n[{c.category}/{c.urgency}/{c.sub_type}] {content[:40]}")
        print(" 초안:", d.draft_reply[:80])

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