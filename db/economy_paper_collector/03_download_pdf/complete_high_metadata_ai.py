from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
TEXT_DIR = PROJECT_ROOT / "data" / "text"

RESOLVED_FILE = METADATA_DIR / "papers_resolved.jsonl"
EXTRACTED_FILE = METADATA_DIR / "papers_extracted.jsonl"

OUTPUT_FILE = METADATA_DIR / "papers_high_completed.jsonl"
REVIEW_FILE = METADATA_DIR / "papers_high_completed_review.jsonl"

ENV_FILE = PROJECT_ROOT / ".env"


# ============================================================
# 설정
# ============================================================

MODEL = "gpt-5-mini"

MAX_WORKERS = 5
MAX_RETRIES = 3

# 전체 논문을 API에 보내는 것이 아니라
# 논문 앞부분만 메타데이터 판별에 사용
MAX_HEAD_CHARS = 15000


# ============================================================
# 환경 변수
# ============================================================

load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY를 찾을 수 없습니다.\n"
        f".env 위치 확인: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


# ============================================================
# JSONL
# ============================================================

def load_jsonl(path: Path) -> list[dict]:
    rows = []

    if not path.exists():
        return rows

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return rows


def append_jsonl(
    path: Path,
    data: dict,
    lock: Lock,
):
    with lock:
        with path.open(
            "a",
            encoding="utf-8",
        ) as f:
            f.write(
                json.dumps(
                    data,
                    ensure_ascii=False,
                )
                + "\n"
            )


# ============================================================
# 유틸
# ============================================================

def first_value(
    row: dict,
    keys: list[str],
):
    for key in keys:
        value = row.get(key)

        if value not in (
            None,
            "",
            [],
            {},
        ):
            return value

    return None


def get_paper_id(row: dict):
    return first_value(
        row,
        [
            "paper_id",
            "id",
        ],
    )


def get_title(row: dict):
    return first_value(
        row,
        [
            "title",
            "resolved_title",
            "final_title",
            "title_candidate",
        ],
    )


def get_confidence(row: dict):
    value = row.get("metadata_status")

    if value is None:
        return ""

    return str(value).upper().strip()


def read_text(
    paper_id: str,
    extracted_row: dict | None,
):
    candidates = []

    if extracted_row:
        for key in [
            "text_path",
            "txt_path",
            "text_file",
        ]:
            value = extracted_row.get(key)

            if value:
                p = Path(value)

                if not p.is_absolute():
                    p = PROJECT_ROOT / p

                candidates.append(p)

    candidates.append(
        TEXT_DIR / f"{paper_id}.txt"
    )

    for path in candidates:
        if path.exists():
            try:
                return path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except Exception:
                pass

    return ""


# ============================================================
# OpenAI 메타데이터 보충
# ============================================================

def analyze_metadata(
    paper_id: str,
    fixed_title: str,
    text: str,
):
    head = text[:MAX_HEAD_CHARS]

    prompt = f"""
다음은 한국어 논문 또는 학위논문의 앞부분입니다.

이 논문의 제목은 이미 다른 방식으로 검증되어 확정되었습니다.

[확정 제목]
{fixed_title}

중요:
- 제목은 수정하거나 새로 추정하지 마세요.
- 반드시 위의 확정 제목을 그대로 반환하세요.
- 이번 작업의 목적은 저자, 연도, 학술지/기관, 학과,
  문서 유형, DOI 등 부족한 메타데이터를 보충하는 것입니다.
- 본문 내용으로 존재하지 않는 정보를 추측하지 마세요.
- 확인할 수 없는 값은 null로 반환하세요.
- 저자가 여러 명이면 authors 배열에 모두 넣으세요.
- document_type은 아래 값 중 하나만 사용하세요.

journal_article
master_thesis
doctoral_thesis
report
policy_document
news
other

confidence:
HIGH = 문서에서 직접 확인됨
MEDIUM = 상당히 유력하지만 약간 불확실
LOW = 확인하기 어려움

JSON만 반환하세요.

반환 형식:

{{
  "title": "{fixed_title}",
  "authors": [],
  "year": null,
  "journal": null,
  "institution": null,
  "department": null,
  "document_type": null,
  "doi": null,
  "confidence": "HIGH",
  "evidence": ""
}}

[문서 앞부분]

{head}
"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 학술 문서 메타데이터 추출기다. "
                            "문서에서 직접 확인할 수 있는 정보만 반환한다. "
                            "절대 존재하지 않는 정보를 추측하지 않는다."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={
                    "type": "json_object",
                },
            )

            content = (
                response
                .choices[0]
                .message
                .content
            )

            result = json.loads(content)

            # 제목은 AI 결과를 신뢰하지 않고
            # 기존 확정 제목으로 강제
            result["title"] = fixed_title
            result["paper_id"] = paper_id

            return result

        except Exception as e:
            last_error = str(e)

            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)

    raise RuntimeError(last_error)


# ============================================================
# main
# ============================================================

def main():

    print("=" * 72)
    print("기존 HIGH 42개 메타데이터 보충")
    print("=" * 72)

    resolved_rows = load_jsonl(
        RESOLVED_FILE
    )

    extracted_rows = load_jsonl(
        EXTRACTED_FILE
    )

    extracted_map = {}

    for row in extracted_rows:
        paper_id = get_paper_id(row)

        if paper_id:
            extracted_map[paper_id] = row

    # --------------------------------------------------------
    # HIGH만 선택
    # --------------------------------------------------------

    high_rows = []

    for row in resolved_rows:
        confidence = get_confidence(row)

        if confidence == "HIGH":
            high_rows.append(row)

    print(
        f"기존 HIGH 대상      : {len(high_rows)}"
    )

    # --------------------------------------------------------
    # 이미 처리된 것 확인
    # --------------------------------------------------------

    completed_rows = load_jsonl(
        OUTPUT_FILE
    )

    completed_ids = {
        get_paper_id(row)
        for row in completed_rows
        if get_paper_id(row)
    }

    pending = []

    for row in high_rows:
        paper_id = get_paper_id(row)

        if not paper_id:
            continue

        if paper_id in completed_ids:
            continue

        pending.append(row)

    print(
        f"이미 처리           : {len(completed_ids)}"
    )

    print(
        f"이번 실행 예정      : {len(pending)}"
    )

    print(
        f"동시 처리 수        : {MAX_WORKERS}"
    )

    if not pending:
        print()
        print("추가 처리할 논문이 없습니다.")
        return

    print()

    output_lock = Lock()
    review_lock = Lock()

    success = 0
    failed = 0

    # --------------------------------------------------------
    # 작업 함수
    # --------------------------------------------------------

    def process(row: dict):

        paper_id = get_paper_id(row)
        fixed_title = get_title(row)

        if not fixed_title:
            raise RuntimeError(
                f"{paper_id}: 확정 제목 없음"
            )

        extracted = extracted_map.get(
            paper_id
        )

        text = read_text(
            paper_id,
            extracted,
        )

        if not text.strip():
            raise RuntimeError(
                f"{paper_id}: TXT 없음"
            )

        result = analyze_metadata(
            paper_id=paper_id,
            fixed_title=fixed_title,
            text=text,
        )

        # 기존 정보 보존
        result["source"] = (
            "deterministic_high_metadata_completion"
        )

        result["original_confidence"] = "HIGH"

        if extracted:
            result["source_filename"] = (
                extracted.get("source_filename")
                or extracted.get("filename")
                or extracted.get("pdf_filename")
            )

            result["text_path"] = (
                extracted.get("text_path")
                or extracted.get("txt_path")
                or extracted.get("text_file")
            )

        return result

    # --------------------------------------------------------
    # 병렬 실행
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {
            executor.submit(
                process,
                row,
            ): row
            for row in pending
        }

        total = len(future_map)
        done = 0

        for future in as_completed(
            future_map
        ):
            row = future_map[future]

            done += 1

            paper_id = get_paper_id(row)

            try:
                result = future.result()

                append_jsonl(
                    OUTPUT_FILE,
                    result,
                    output_lock,
                )

                success += 1

                print(
                    f"[{done}/{total}] "
                    f"{paper_id} | "
                    f"{result.get('confidence')} | "
                    f"{result.get('title')}"
                )

            except Exception as e:

                failed += 1

                error_row = {
                    "paper_id": paper_id,
                    "title": get_title(row),
                    "error": str(e),
                }

                append_jsonl(
                    REVIEW_FILE,
                    error_row,
                    review_lock,
                )

                print(
                    f"[ERROR {done}/{total}] "
                    f"{paper_id}: {e}"
                )

    # --------------------------------------------------------
    # 최종 집계
    # --------------------------------------------------------

    all_completed = load_jsonl(
        OUTPUT_FILE
    )

    high = 0
    medium = 0
    low = 0

    for row in all_completed:
        confidence = str(
            row.get(
                "confidence",
                "",
            )
        ).upper()

        if confidence == "HIGH":
            high += 1

        elif confidence == "MEDIUM":
            medium += 1

        else:
            low += 1

    print()
    print("=" * 72)
    print("기존 HIGH 메타데이터 보충 종료")
    print("=" * 72)

    print(
        f"이번 실행 성공      : {success}"
    )

    print(
        f"이번 실행 실패      : {failed}"
    )

    print()

    print(
        f"보충 결과 HIGH      : {high}"
    )

    print(
        f"보충 결과 MEDIUM    : {medium}"
    )

    print(
        f"보충 결과 LOW       : {low}"
    )

    print()

    print("결과 파일:")
    print(OUTPUT_FILE)

    if failed:
        print()
        print("검토 파일:")
        print(REVIEW_FILE)


if __name__ == "__main__":
    main()