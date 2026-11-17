"""외부 API 호출 재시도 공통 함수"""
import time
from google.genai import errors

MAX_RETRY = 3
DELAY_BETWEEN = 10
RETRY_CODES = {429,503}

def call_with_retry(func, *args, **kwargs):
    """일시적인 에러면 기다렸다가 다시 시도, 그 외 에러는 그대로 올림"""
    for attempt in range(1, MAX_RETRY +1):
        try:
            return func(*args, **kwargs)
        except errors.APIError as e:
            if e.code == 429 and "PerDay" in str(e):
                raise
            if e.code not in RETRY_CODES or attempt == MAX_RETRY:
                raise
            wait = 20 * attempt
            print(f"    일시 오류({e.code}), {wait}초 후 재시도 ({attempt}/ {MAX_RETRY})")
            time.sleep(attempt)