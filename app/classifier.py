from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

from google import genai
from app.schemas import InquiryClassification

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

PROMPT_PATH = ROOT_DIR / "prompts" / "classify_v1.txt"
MODEL= "gemini-3.1-flash-lite"


@lru_cache(maxsize=1)
def _get_clinet() -> genai.Client:
    return genai.Client()


def classify(category: str, content: str) -> InquiryClassification:
    """문의 1건을 분류해서 InquiryClassification으로 돌려줌"""

    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(category=category, content=content)

    response = _get_clinet().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": InquiryClassification
        },

    )

    return InquiryClassification.model_validate_json(response.text)

