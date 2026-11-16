from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from app.schemas import InquiryClassification,InquiryDraft

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

PROMPT_PATH = ROOT_DIR / "prompts" / "draft_v2.txt"
MODEL= "gemini-3.1-flash-lite"

@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client()

def draft(content: str, classification: InquiryClassification, prompt_path: Path = PROMPT_PATH) -> InquiryDraft:
    """ 문의 내용과 분류 결과를 답변 초안을 만들어 돌려줌"""

    missing = ", ".join(classification.missing_info) or "없음"
    template = prompt_path.read_text(encoding="utf-8")

    prompt = template.format(
        category = classification.category,
        urgency = classification.urgency,
        sub_type = classification.sub_type,
        missing_info = missing,
        content = content
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