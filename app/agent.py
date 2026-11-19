"""문의 조사 에이전트: 도구로 사실을 모으고, 답변 drafter(v6)가 작성"""
import json
import sys
from pathlib import Path
from google.genai import types
from app import classifier, drafter, tools
from app.classifier import _get_clinet
from app.retry import call_with_retry
from datetime import datetime,timedelta, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "agent_v2.txt"
MODEL = classifier.MODEL
MAX_TOOL_CALLS = 5
KST = timezone(timedelta(hours=9))

TOOL_DECLS = [
    types.FunctionDeclaration(
        name="get_user_posts",
        description="문의한 사용자의 최근 글 10개와 상태(공개/본인 삭제/숨김)를 조회. 글이 사라졌다. 안 보인다는 문의에 사용."
    ),
    types.FunctionDeclaration(
        name="get_user_profile",
        description="문의한 사용자의 신뢰 레벨과 남은 유저네임 변경권 개수를 조회, 레벨이나 유저네임 변경 문의에 사용."
    ),
    types.FunctionDeclaration(
        name="get_reports",
        description="문의한 사용자의 글에 접수된 신고 건수와 사유를 조회, 글이 숨겨졌거나 신고 관련 문의에 사용."
    ),
    types.FunctionDeclaration(
        name="search_policy",
        description="운영 정책과 FAQ에서 관련 문단을 검색, 앱 규칙이나 사용법을 안내해야 할 때 사용.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="검색할 질문, 한국어 한 문장")
            },
            required=["query"]
        )
    )
]

def _to_facts(name:str, result:dict) -> list[dict]:
    """도구 결과를 drafter가 읽는 근거 형식({source, title, text})으로 변환"""
    if name == "search_policy":
        return result.get("results", [])
    return [{"source":"조회", "title":name, "text": json.dumps(result, ensure_ascii=False)}]

def investigate(uid:str, content:str, c, run_tool=tools.run_tool) -> tuple[list[dict], list[dict]]:
    """도구를 반복 호출해 사실을 모음. (근거 목록, 호출 기록)을 반환"""
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        today=datetime.now(KST).strftime("%Y-%m-%d"),
        category = c.category, urgency = c.urgency, content=content
    )
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=TOOL_DECLS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0
    )
    facts, trace = [], []
    summary = ""

    while len(trace) < MAX_TOOL_CALLS:
        resp = call_with_retry(
            lambda: _get_clinet().models.generate_content(model=MODEL, contents=contents, config=config)
        )
        calls = resp.function_calls or []
        if not calls:
            summary = (resp.text or "").strip()
            break

        contents.append(resp.candidates[0].content)
        reply_parts = []
        for call in calls[: MAX_TOOL_CALLS - len(trace)]:
            args = dict(call.args or {})
            result = run_tool(call.name, uid, args)
            trace.append({
                "tool": call.name,
                "args": args,
                "summary": json.dumps(result, ensure_ascii=False)[:200]
            })
            facts.extend(_to_facts(call.name, result))
            reply_parts.append(types.Part.from_function_response(name=call.name, response=result))

        contents.append(types.Content(role="user", parts=reply_parts))

    if trace and summary:
        facts.insert(0, {"source":"조사 요약", "title": "agent", "text": summary})
    
    return facts, trace

def run_agent(uid:str, category:str, content:str, run_tool=tools.run_tool):
    """분류 -> 조사 -> 작성. (분류, 초안, 근거, 호출 기록)을 반환"""
    c = call_with_retry(classifier.classify, category, content)
    facts, trace = investigate(uid, content, c,run_tool)
    d = call_with_retry(drafter.draft, content, c, sources=facts)
    return c, d, facts, trace


if __name__ == "__main__":
    uid, content = sys.argv[1], sys.argv[2]
    category = sys.argv[3] if len(sys.argv) > 3 else "기타"


    c,d, facts, trace = run_agent(uid, category, content)
    print(f"[분류] {c.category}/ {c.urgency}")
    for i, t in enumerate(trace, 1):
        print(f"[도구 {i}] {t['tool']} {t['args']}")
        print(f"    -> {t['summary']}")
        if not trace:
            print("[도구] 호출 없음")
        if facts and facts[0]["source"] == "조사 요약":
            print(f"[요약] {facts[0]['text']}")

    print(f"[초안] {d.draft_reply}")