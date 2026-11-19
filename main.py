"""Cloud Functions 진입점: 문의 생성 트리거 + 매일 재처리"""
import os
import time

from firebase_functions import firestore_fn, scheduler_fn, options
from firebase_functions.params import SecretParam

AX_GEMINI_KEY = SecretParam("AX_GEMINI_API_KEY")
SLACK_URL = SecretParam("SLACK_WEBHOOK_URL")

options.set_global_options(region="us-central1", max_instances=1, memory=options.MemoryOption.MB_512)

def _prepare_evn() -> None:
    """genai.Client()가 읽는 이름으로 키를 옮겨둠 (클라이언트 생성 전에 호출)"""
    os.environ["GEMINI_API_KEY"] = AX_GEMINI_KEY.value

def _handle(inq:dict) -> None:
    """문의 1건 처리 후 긴급하면 슬랙 알림"""
    from app.pipeline import process_one
    from app.notify import send_slack

    f = process_one(inq, use_agent=True, write=True)
    if f["aiUrgency"] == "높음":
        send_slack(
            f"🚨 긴급 문의 [{f['aiCategory']}/{f['aiSubType']}]\n"
            f"> {inq.get('content', '')[:80]}\n"
            f"관리자 웹 문의 탭에서 확인해 주세요."
        )

@firestore_fn.on_document_created(
    document="inquiries/{inquiryId}",
    secrets=[AX_GEMINI_KEY, SLACK_URL],
    timeout_sec=120
)
def on_inquiry_created(event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> None:
    """문의가 생성되면 AI 초안 작성"""
    if event.data is None:
        return
    inq = event.data.to_dict() or {}
    inq["id"] = event.params["inquiryId"]

    if inq.get("aiDraft") or inq.get("status") != "pending":
        return

    _prepare_evn()
    try:
        _handle(inq)
    except Exception as e:
        print(f"[실패] {inq['id']}: {e}")
        from app.notify import send_slack
        send_slack(f"⚠️ AI 초안 실패 ({inq['id']}), 내일 09시에 다시 시도해요: {str(e)[:100]}")


@scheduler_fn.on_schedule(
    schedule = "0 9 * * *",
    timezone=scheduler_fn.Timezone("Asia/Seoul"),
    secrets = [AX_GEMINI_KEY, SLACK_URL],
    timeout_sec=540
)
def retry_pending(event: scheduler_fn.ScheduledEvent) -> None:
    """매일 09시: 초안 없는 pending 문의를 다시 처리"""
    from app.firebase_repo import fetch_pending
    from app.retry import DELAY_BETWEEN

    _prepare_evn()
    for inq in fetch_pending(10):
        try:
            _handle(inq)
        except Exception as e:
            print(f"[재처리 실패] {inq["id"]} : {e}")
        time.sleep(DELAY_BETWEEN)