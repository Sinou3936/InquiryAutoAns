"""슬랙 Incoming Webhook 알림"""
import json
import os
import urllib.request

def send_slack(text:str) -> None:
    """슬랙 채널로 메시지 전송. 실패해도 문의 처리는 막지 않음"""
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("SLACK_WEBHOOK_URL 없음, 알림 건너뜀.")
        return
    req = urllib.request.Request(
        url,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"슬랙 알림 실패: {e}")
