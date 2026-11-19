import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from pathlib import Path
from functools import lru_cache

from datetime import datetime, timezone
from google.cloud.firestore_v1.base_query import FieldFilter


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path(__file__).resolve().parent.parent
KEY_PATH = ROOT_DIR / "secrets" / "serviceAccountKey.json"

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)

@lru_cache(maxsize=1)
def get_db():
    if not firebase_admin._apps:
        if KEY_PATH.exists():
            firebase_admin.initialize_app(credentials.Certificate(str(KEY_PATH)))
        else:
            firebase_admin.initialize_app()
            
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
        if data.get("aiDraft"):
            continue
        data["id"] = doc.id
        result.append(data)
    
    result.sort(key=lambda d: d.get("createdAt") or _OLDEST)
    return result[:limit]

def save_ai_draft(inquiry_id: str, fields: dict) -> None:
    """AI 결과를 문의 문서에 추가 (기존 필드는 유지)"""

    get_db().collection("inquiries").document(inquiry_id).update(fields)

def fetch_user_posts(uid:str, limit: int = 10) -> list[dict]:
    """사용자가 쓴 글을 최신순으로 가져옴 (삭제,숨김 포함)"""
    docs = (
        get_db().collection("posts")
        .where(filter=FieldFilter("authorId","==",uid))
        .stream()
    )

    posts = [{"id": d.id, **d.to_dict()} for d in docs]
    posts.sort(key=lambda p: p.get("createdAt") or _OLDEST, reverse=True)
    return posts[:limit]

def fetch_reports_for_posts(post_ids: list[str]) -> list[dict]:
    """주어진 글들에 접수된 신고를 가져옴"""
    if not post_ids:
        return []
    docs = (
        get_db().collection("reports")
        .where(filter=FieldFilter("targetType", "==", "post"))
        .where(filter=FieldFilter("targetId","in", post_ids[:30]))
        .stream()
    )

    return [d.to_dict() for d in docs]

def fetch_user(uid:str) -> dict:
    """사용자 문서를 가져옴 (없으면 빈 dict)"""
    snap = get_db().collection("users").document(uid).get()
    return snap.to_dict() or {}