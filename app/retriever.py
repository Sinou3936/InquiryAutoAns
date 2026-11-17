import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

POLICY_DIR = ROOT_DIR / "policies"
INDEX_PATH = ROOT_DIR / "data" / "index.json"
EMBED_MODEL = "gemini-embedding-001"

@lru_cache
def _get_client() -> genai.Client:
    return genai.Client()

def load_chunks() -> list[dict]:
    """정책 문서를 '## 제목' 단위로 잘라 조각 목록으로 만든다."""
    chunks = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        title, lines = None, []
        for line in path.read_text(encoding="utf-8").splitlines(): 
                if line.startswith("## "):
                    if title:
                        chunks.append(_make_chunk(path.stem,title,lines))
                    title, lines = line[3:].strip(), []
                elif title:
                    lines.append(line)
        if title:
             chunks.append(_make_chunk(path.stem,title,lines))
    return chunks

def _make_chunk(source: str, title: str, lines: list[str]) -> dict:
     body = "\n".join(lines).strip()
     return {"source": source, "title": title, "text": f"{title}\n{body}"}

def _embed(texts: list[str], task_type: str) -> np.ndarray:
     result = _get_client().models.embed_content(
          model=EMBED_MODEL,
          contents=texts,
          config=types.EmbedContentConfig(task_type=task_type)
     )
     vertors = np.array([e.values for e in result.embeddings], dtype=np.float32)

     return vertors / np.linalg.norm(vertors, axis=1, keepdims=True)

def _hash(chunks: list[dict]) -> str:
     joined = "".join(c["text"] for c in chunks)
     return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@lru_cache
def _load_index() -> tuple[list[dict], np.ndarray]:
    chunks = load_chunks()
    digest = _hash(chunks)

    if INDEX_PATH.exists():
        try:
            saved = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if saved["hash"] == digest:
                return saved["chunks"], np.array(saved["vectors"], dtype=np.float32)
        except (json.JSONDecodeError, KeyError):
            print("인덱스 파일이 깨져 있어서 새로 만듭니다.")

    print(f"인덱스 생성: 조각 {len(chunks)}개 임베딩 중...")
    vectors = _embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
         json.dumps({"hash": digest, "chunks": chunks, "vectors": vectors.tolist()}, ensure_ascii=False)
         ,encoding="utf-8"
    )

    return chunks,vectors

def search(query: str, k: int = 3) -> list[dict]:
     chunks, vectors = _load_index()
     q = _embed([query],"RETRIEVAL_QUERY")[0]
     scores = vectors @ q
     top = np.argsort(scores)[::-1][:k]
     return [{**chunks[i], "score": float(scores[i])} for i in top ]


if __name__ == "__main__":
     for q in ["탈퇴하면 글도 지워지나요?", "닉네임 바꾸고 싶어요.", "글이 사라졌어요","광고 없애는 법"]:
          print(f"\n 질문: {q}")
          for r in search(q):
               print(f" {r['score']:.3f} [{r['source']}] {r['title']}")
