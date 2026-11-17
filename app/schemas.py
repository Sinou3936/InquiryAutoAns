from typing import Literal
from pydantic import BaseModel, Field

class InquiryClassification(BaseModel):
    """문의 1건에 대한 AI 분석 결과"""

    category: Literal["버그 신고","기능 건의","결제 문의","기타"]
    urgency: Literal["높음","보통","낮음"]

    sub_type: str = Field(description="문의의 구체적인 유형 10자 이내")

    missing_info: list[str] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0)

    needs_policy: bool = Field(
        description="앱의 정책·규칙·기능 사용법을 안내해야 답할 수 있는 문의면 true, 버그 신고나 기능 건의처럼 정책 안내가 필요 없으면 false"
    )


class InquiryDraft(BaseModel):
    """drafter.py가 돌려줄 답변 초안"""

    draft_reply: str = Field(description="정중한 존댓말 답변 초안")