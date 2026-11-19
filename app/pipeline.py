import argparse
import time

from firebase_admin import firestore
from app import agent, classifier, drafter, retriever
from app.retry import DELAY_BETWEEN, call_with_retry
from app.firebase_repo import fetch_pending, get_db, save_ai_draft

def _draft_basic(inq: dict):
    """기존 경로: 분류 -> (필요시) 정책 검색 -> 초안"""
    content = inq.get("content","")
    c = call_with_retry(classifier.classify, inq.get("category","기타"), content)
    sources = call_with_retry(retriever.search, content) if c.needs_policy else []
    d = call_with_retry(drafter.draft, content, c, sources=sources)
    return c, d, sources, []

def _draft_agent(inq: dict):
    """에이전트 경로: 분류 -> 도구 조사 -> 초안"""
    if not inq.get("uid"):
        return _draft_basic
    return agent.run_agent(inq["uid"], inq.get("category","기타"), inq.get("content",""))


def build_fields(c, d, sources: list[dict], trace: list[dict]) -> dict:
    """분류/초안/근거/조사기록을 Firebase 저장 형식으로 변환"""
    version = f"{classifier.PROMPT_PATH.stem}+{drafter.PROMPT_PATH.stem}"
    if trace:
        version += f"+{agent.PROMPT_PATH.stem}"
            
    return {
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
            "aiSources": [
                {
                    "source": s.get("source"),
                    "title": s.get("title"),
                    "score": round(s["score"],3) if s.get("score") is not None else None
                 }
                for s in sources
            ],
            "aiTrace": trace
    }

def process_one(inq:dict, use_agent:bool = True, write:bool =True) -> dict:
    """문의 1건 처리, 로컬 run과 Clound Function이 같이 쓰는 공통 함수"""
    c, d, sources, trace = _draft_agent(inq) if use_agent else _draft_basic(inq)
    fields = build_fields(c,d, sources, trace)
    if write:
        save_ai_draft(inq["id"],trace)
    return fields

def run(limit: int, write:bool, use_agent:bool) -> None:
    print("연결된 프로젝트:", get_db().project)
    print("모드:", "저장" if write else "확인만(저장 안함)", "/", "에이전트" if use_agent else "기본" )

    inquiries = fetch_pending(limit) 
    ok,fail =0, 0

    for inq in inquiries:
        content = inq.get("content", "")
        try:
            f = process_one(inq, use_agent, write)
        except Exception as e:
            print(f"[실패] {inq['id']}: {str(e)[:100]}")
            fail += 1
            time.sleep(DELAY_BETWEEN)
            continue

        print(f"\n[{f['aiCategory']}/{f['aiUrgency']}/{f['aiSubType']}] {content[:40]}")
        for t in f["aiTrace"]:
            print(f"    도구: {t['tool']}")
        print(" 초안:", f["aiDraft"][:80])

        for s in f["aiSources"]:
            print(f"    근거: {s['source']} / {s['title']}")

            if write:
                ok += 1
            time.sleep(DELAY_BETWEEN)

    print(f"\n총 {len(inquiries)}건 중 {ok}건 저장, {fail}건 실패")     


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--write", action="store_true", help="붙이면 Firestore에 저장")
    parser.add_argument("--agent", action="store_true", help="붙이면 도구 조사 후 초안 작성")
    args = parser.parse_args()
    run(args.limit, args.write, args.agent)