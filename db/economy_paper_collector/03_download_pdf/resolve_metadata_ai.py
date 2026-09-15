from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
META_DIR = PROJECT_ROOT / "data" / "metadata"

REVIEW_FILE = META_DIR / "papers_metadata_review.jsonl"

AI_OUTPUT_FILE = META_DIR / "papers_ai_resolved.jsonl"
AI_REVIEW_FILE = META_DIR / "papers_ai_review.jsonl"


# ============================================================
# 환경변수
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY가 없습니다.\n"
        "프로젝트 최상위 .env 파일을 확인하세요."
    )

client = OpenAI(api_key=api_key)


# ============================================================
# 설정
# ============================================================

MODEL = "gpt-5-mini"

# 전체 논문이 아니라 앞부분만 전달
MAX_HEAD_CHARS = 15_000

# 동시에 처리할 논문 수
MAX_WORKERS = 5

# API 오류 발생 시 최대 재시도
MAX_RETRIES = 3

# 여러 Thread가 동시에 JSONL을 쓰지 않도록 보호
write_lock = Lock()


# ============================================================
# JSONL
# ============================================================

def read_jsonl(path: Path) -> list[dict]:

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
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:
                print(
                    f"[WARNING] JSON 파싱 실패: {path}"
                )

    return rows


def append_jsonl(
    path: Path,
    row: dict,
) -> None:

    # Thread-safe 파일 저장
    with write_lock:

        with path.open(
            "a",
            encoding="utf-8",
        ) as f:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

            # 즉시 디스크 반영
            f.flush()


# ============================================================
# 기존 완료 paper_id
# ============================================================

def load_completed_ids() -> set[str]:

    completed = set()

    if not AI_OUTPUT_FILE.exists():
        return completed

    for row in read_jsonl(
        AI_OUTPUT_FILE
    ):

        paper_id = row.get(
            "paper_id"
        )

        if paper_id:
            completed.add(
                paper_id
            )

    return completed


# ============================================================
# AI JSON 파싱
# ============================================================

def parse_ai_json(
    text: str,
) -> dict[str, Any]:

    text = text.strip()

    # ```json
    if text.startswith("```"):

        text = text.replace(
            "```json",
            "",
            1,
        )

        text = text.replace(
            "```",
            "",
        )

        text = text.strip()

    # 앞뒤에 설명이 붙었을 경우 JSON 영역 추출
    first = text.find("{")
    last = text.rfind("}")

    if first != -1 and last != -1:
        text = text[
            first:last + 1
        ]

    return json.loads(text)


# ============================================================
# AI 분석
# ============================================================

def analyze_metadata(
    row: dict,
    text: str,
) -> dict:

    title_candidates = row.get(
        "title_candidates",
        {},
    )

    filename_candidate = None
    pdf_candidate = None

    if isinstance(
        title_candidates,
        dict,
    ):

        filename_candidate = (
            title_candidates.get(
                "filename"
            )
        )

        pdf_candidate = (
            title_candidates.get(
                "pdf_metadata"
            )
        )

    existing_kci_candidate = row.get(
        "kci_match_title"
    )

    document_head = text[
        :MAX_HEAD_CHARS
    ]

    prompt = f"""
다음은 한국 학술자료 PDF에서 추출한 앞부분 텍스트입니다.

당신의 역할은 문서에 실제로 명시되어 있는 bibliographic metadata를
추출하는 것입니다.

절대로 제목을 새로 만들거나 요약해서는 안 됩니다.
초록이나 본문의 문장을 제목으로 사용해서도 안 됩니다.

실제 문서에 명시되어 있는 정보만 반환하세요.
확실하지 않은 값은 null로 반환하세요.

특히 제목은 다음 위치를 우선 확인하세요.

- 논문 첫 페이지의 실제 제목
- 학위논문 표지
- 학술지 논문 첫 페이지
- 국문 제목과 영문 제목이 함께 있다면 국문 제목 우선

기존 시스템 후보가 아래에 있습니다.
후보가 틀릴 수도 있으므로 반드시 문서와 비교하세요.

파일명 제목 후보:
{filename_candidate}

PDF metadata 제목 후보:
{pdf_candidate}

KCI metadata 후보:
{existing_kci_candidate}

반환 JSON:

{{
  "title": "실제 국문 제목 또는 null",
  "authors": ["저자1", "저자2"],
  "year": 2024,
  "journal": "학술지명 또는 null",
  "institution": "대학교/연구기관 또는 null",
  "department": "학과 또는 null",
  "document_type": "journal_article | master_thesis | doctoral_thesis | report | policy_document | news | other",
  "doi": "DOI 또는 null",
  "confidence": "HIGH | MEDIUM | LOW",
  "evidence": "판단 근거를 짧게 설명"
}}

규칙:

1. authors는 반드시 배열
2. 저자 확인 불가 시 []
3. year는 숫자 또는 null
4. 제목 확인 불가 시 null
5. 제목 뒤 페이지 번호 제거
6. *, † 등의 각주 기호 제거
7. 권/호/페이지를 제목에 포함하지 않음
8. 본문/초록 문장을 제목으로 오인하지 않음
9. 문서에 없는 내용을 추측하지 않음
10. JSON 이외의 문장은 출력하지 않음

================ DOCUMENT ================

{document_head}

================ END ================
""".strip()

    response = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    return parse_ai_json(
        response.output_text
    )


# ============================================================
# 논문 1개 처리
# ============================================================

def process_paper(
    row: dict,
) -> dict:

    paper_id = row.get(
        "paper_id"
    )

    source_filename = row.get(
        "source_filename"
    )

    text_file_relative = row.get(
        "text_file"
    )

    if not text_file_relative:

        return {
            "success": False,
            "paper_id": paper_id,
            "source_filename": source_filename,
            "error": "NO_TEXT_FILE",
        }

    text_path = (
        PROJECT_ROOT
        / text_file_relative
    )

    if not text_path.exists():

        return {
            "success": False,
            "paper_id": paper_id,
            "source_filename": source_filename,
            "error": (
                f"TEXT_FILE_NOT_FOUND: "
                f"{text_path}"
            ),
        }

    text = text_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            ai_result = analyze_metadata(
                row,
                text,
            )

            output_row = dict(row)

            output_row[
                "ai_metadata"
            ] = ai_result

            output_row[
                "ai_model"
            ] = MODEL

            confidence = str(
                ai_result.get(
                    "confidence",
                    "LOW",
                )
            ).upper()

            if confidence not in {
                "HIGH",
                "MEDIUM",
                "LOW",
            }:
                confidence = "LOW"

            output_row[
                "metadata_status"
            ] = (
                "AI_"
                + confidence
            )

            # 성공 즉시 저장
            append_jsonl(
                AI_OUTPUT_FILE,
                output_row,
            )

            return {
                "success": True,
                "paper_id": paper_id,
                "source_filename": source_filename,
                "metadata": ai_result,
            }

        except Exception as e:

            last_error = str(e)

            if attempt < MAX_RETRIES:
                time.sleep(
                    2 * attempt
                )

    error_row = {
        "paper_id": paper_id,
        "source_filename": source_filename,
        "error": last_error,
    }

    append_jsonl(
        AI_REVIEW_FILE,
        error_row,
    )

    return {
        "success": False,
        "paper_id": paper_id,
        "source_filename": source_filename,
        "error": last_error,
    }


# ============================================================
# 결과 집계
# ============================================================

def count_results() -> dict[str, int]:

    counts = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
        "OTHER": 0,
    }

    for row in read_jsonl(
        AI_OUTPUT_FILE
    ):

        ai = row.get(
            "ai_metadata",
            {},
        )

        confidence = str(
            ai.get(
                "confidence",
                "LOW",
            )
        ).upper()

        if confidence in counts:
            counts[
                confidence
            ] += 1

        else:
            counts[
                "OTHER"
            ] += 1

    return counts


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 72)
    print(
        "AI Metadata 병렬 판별"
    )
    print("=" * 72)

    review_rows = read_jsonl(
        REVIEW_FILE
    )

    completed_ids = (
        load_completed_ids()
    )

    remaining_rows = [
        row
        for row in review_rows
        if row.get("paper_id")
        not in completed_ids
    ]

    print(
        f"전체 REVIEW       : "
        f"{len(review_rows)}"
    )

    print(
        f"이미 처리         : "
        f"{len(completed_ids)}"
    )

    print(
        f"이번 실행 예정    : "
        f"{len(remaining_rows)}"
    )

    print(
        f"동시 처리 수      : "
        f"{MAX_WORKERS}"
    )

    print()

    if not remaining_rows:

        print(
            "추가 처리할 논문이 없습니다."
        )

        counts = count_results()

        print()
        print(
            f"AI HIGH   : {counts['HIGH']}"
        )
        print(
            f"AI MEDIUM : {counts['MEDIUM']}"
        )
        print(
            f"AI LOW    : {counts['LOW']}"
        )

        return

    success = 0
    failed = 0

    total = len(
        remaining_rows
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {
            executor.submit(
                process_paper,
                row,
            ): row
            for row in remaining_rows
        }

        for number, future in enumerate(
            as_completed(
                future_map
            ),
            start=1,
        ):

            row = future_map[
                future
            ]

            try:

                result = future.result()

            except Exception as e:

                failed += 1

                print(
                    f"[{number}/{total}] "
                    f"{row.get('paper_id')} "
                    f"UNEXPECTED ERROR"
                )

                print(
                    f"    {e}"
                )

                continue

            if result[
                "success"
            ]:

                success += 1

                metadata = result[
                    "metadata"
                ]

                print(
                    f"[{number}/{total}] "
                    f"{result['paper_id']} "
                    f"OK"
                )

                print(
                    f"    TITLE : "
                    f"{metadata.get('title')}"
                )

                print(
                    f"    AUTHOR: "
                    f"{metadata.get('authors')}"
                )

                print(
                    f"    YEAR  : "
                    f"{metadata.get('year')}"
                )

                print(
                    f"    TYPE  : "
                    f"{metadata.get('document_type')}"
                )

                print(
                    f"    CONF  : "
                    f"{metadata.get('confidence')}"
                )

            else:

                failed += 1

                print(
                    f"[{number}/{total}] "
                    f"{result['paper_id']} "
                    f"FAILED"
                )

                print(
                    f"    ERROR : "
                    f"{result.get('error')}"
                )

            print()

    counts = count_results()

    print()
    print("=" * 72)
    print(
        "AI Metadata 병렬 분석 종료"
    )
    print("=" * 72)

    print(
        f"이번 실행 성공    : "
        f"{success}"
    )

    print(
        f"이번 실행 실패    : "
        f"{failed}"
    )

    print()

    print(
        f"누적 AI HIGH      : "
        f"{counts['HIGH']}"
    )

    print(
        f"누적 AI MEDIUM    : "
        f"{counts['MEDIUM']}"
    )

    print(
        f"누적 AI LOW       : "
        f"{counts['LOW']}"
    )

    if counts[
        "OTHER"
    ]:

        print(
            f"기타 confidence   : "
            f"{counts['OTHER']}"
        )

    print()
    print(
        "결과 파일:"
    )
    print(
        AI_OUTPUT_FILE
    )

    print()
    print(
        "※ 성공한 논문은 즉시 저장됩니다."
    )

    print(
        "※ 중간에 종료되어도 재실행하면 "
        "완료된 paper_id는 자동으로 건너뜁니다."
    )


if __name__ == "__main__":
    main()