import argparse
import json
from datetime import datetime
from pathlib import Path

from app import classifier, drafter
from app.pipeline import call_with_retry, DELAY_BETWEEN
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT_DIR / "eval" / "golden.jsonl"
RESULT_DIR = ROOT_DIR / "eval" / "results"
PROMPT_DIR = ROOT_DIR / "prompts"

MAX_LEN = 80

FORBIDDEN = [
    "조사하고","조사 중","확인 중", "처리해 드리","처리하겠",
    "처리되었","환불해 드리", "환불 처리", "수정 하겠",
    "해결하겠","반영하겠","추가하겠","보상"
]

def load_golden() -> list[dict]:
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def find_forbidden(text: str) -> list[str]:
    return [w for w in FORBIDDEN if w in text]

def run(draft_versions: list[str]) -> None:
    cases = load_golden()
    rows = []

    for i, case in enumerate(cases, 1):
        print(f"[{i}]/{len(cases)} {case['id']}")
        row = {**case, "drafts": {}}
        try:
            c = call_with_retry(classifier.classify, case["user_category"], case["content"])
            row.update(
                pred_category = c.category,
                pred_urgency = c.urgency,
                confidence = c.confidence,
                missing_info = c.missing_info
            )
            for v in draft_versions:
                path = PROMPT_DIR / f"{v}.txt"
                d = call_with_retry(drafter.draft, case["content"], c ,path)
                text = d.draft_reply
                row["drafts"][v] = {
                    "text": text,
                    "length": len(text),
                    "forbidden": find_forbidden(text)
                }
        except Exception as e:
            print(f" 실패 : {str(e)[:100]}")
            row["error"] = str(e)
        rows.append(row)
        time.sleep(DELAY_BETWEEN)
    summary = summarize(rows, draft_versions)
    save(rows, summary)
    print_summary(summary)

def summarize(rows: list[dict], draft_versions: list[str]) -> dict:
    ok =  [r for r in rows if "error" not in r]
    n = len(ok) or 1
    trap = [r for r in ok if r["user_category"] != r["expected_category"]]

    summary = {
        "total": len(rows),
        "failed": len(rows) - len(ok),
        "category_acc": sum(r["pred_category"] == r["expected_category"] for r in ok) / n,
        "urgency_acc": sum(r["pred_urgency"] == r["expected_urgency"] for r in ok) / n,
        "trap_fixed": sum(r["pred_category"] == r["expected_category"] for r in trap) / (len(trap) or 1),
        "drafts": {}
    }

    for v in draft_versions:
        ds =[r["drafts"][v] for r in ok if v in r["drafts"]]
        m = len(ds) or 1
        summary["drafts"][v] = {
            "within_80_rate": sum(d["length"] <= MAX_LEN for d in ds) / m,
            "forbidden_rate": sum(bool(d["forbidden"]) for d in ds) / m,
            "avg_length": sum(d["length"] for d in ds) / m
        }

    return summary


def save(rows: list[dict], summary: dict) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = RESULT_DIR / f"eval_{stamp}.json"
    data = {"model": classifier.MODEL, "summary": summary, "rows": rows}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out}")

def print_summary(s: dict) -> None:
    print(f"\n 총 {s['total']}건 (실패 {s['failed']}건 )")
    print(f"카테고리 정확도 {s['category_acc']:.0%} / 긴급도 정확도{s['urgency_acc']:.0%} / 잘못 고른 카테고리 교정 {s['trap_fixed']:.0%}")
    for v,d in s["drafts"].items():
        print(f"[{v}] 80자 이내 {d['within_80_rate']:.0%} / 지어낸 약속 {d['forbidden_rate']:.0%} / 평균 {d['avg_length']:.0f}자")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drafts", nargs="+", default=["draft_v1", "draft_v2"])
    args = parser.parse_args()
    run(args.drafts)