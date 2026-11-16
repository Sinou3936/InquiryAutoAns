import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from pathlib import Path
from functools import lru_cache

from google.cloud.firestore_v1.base_query import FieldFilter


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path(__file__).resolve().parent.parent
KEY_PATH = ROOT_DIR / "secrets" / "serviceAccountKey.json"

if not KEY_PATH.exists():
    raise FileNotFoundError(f"Service account key file not found at {KEY_PATH}")

@lru_cache(maxsize=1)
def get_db():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(KEY_PATH)))
        return firestore.client()

def fetch_pending(limit: int = 10) -> list[dict]:
    """답변 대기 중이고 아직 AI 초안이 없는 문의 목록"""

    docs = (get_db().collection("inquiries")
                    .where(filter=FieldFilter("status","==","pending"))
                    .limit(limit * 3)
                    .stream()
    )
    result = []
    for doc in docs:
        data = doc.to_dict()
        if data.get("ai_draft"):
            continue
        data["id"] = doc.id
        result.append(data)
    
    result.sort(key=lambda d: d.get("createdAt") or 0)
    return result[:limit]

def save_ai_draft(inquiry_id: str, fields: dict) -> None:
    """AI 결과를 문의 문서에 추가 (기존 필드는 유지)"""

    get_db().collection("inquiries").document(inquiry_id).update(fields)
