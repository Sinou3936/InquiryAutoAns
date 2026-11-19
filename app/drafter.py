from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from app.schemas import InquiryClassification,InquiryDraft

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env.local")

PROMPT_PATH = ROOT_DIR / "prompts" / "draft_v6.txt"
MODEL= "gemini-3.1-flash-lite"

@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client()

def draft(
        content: str, 
        classification: InquiryClassification, 
        prompt_path: Path = PROMPT_PATH,
        sources: list[dict] | None = None,
    ) -> InquiryDraft:
    """ 문의 내용과 분류 결과를 답변 초안을 만들어 돌려줌"""

    #missing = ", ".join(classification.missing_info) or "없음"
    template = prompt_path.read_text(encoding="utf-8")

    source_text = "\n\n".join(
        f"[{s['source']}] {s['text']}" for s in (sources or [])
    ) or "없음"

    prompt = template.format(
        category = classification.category,
        urgency = classification.urgency,
        sub_type = classification.sub_type,
        missing_info = ", ".join(classification.missing_info) or "없음",
        content = content,
        sources = source_text,
    )

    response = _get_client().models.generate_content(
        model = MODEL,
        contents = prompt,
        config = {
            "response_mime_type": "application/json",
            "response_schema": InquiryDraft
        }
    )

    return InquiryDraft.model_validate_json(response.text)


if __name__ == "__main__":
    from app.classifier import classify
    from app import retriever

    content = "회원 탈퇴하면 제가 쓴 글도 다 지워지나요?"
    c = classify("기타", content)
    sources = retriever.search(content)
    v2 = draft(content, c, ROOT_DIR / "prompts" / "draft_v2.txt")
    v3 = draft(content, c, ROOT_DIR / "prompts" / "draft_v3.txt", sources)
    print("v2:", v2.draft_reply)
    print("v3:", v3.draft_reply)