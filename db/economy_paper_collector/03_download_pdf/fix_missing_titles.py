from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

VERIFIED_FILE = METADATA_DIR / "papers_verified.jsonl"
AI_FILE = METADATA_DIR / "papers_ai_resolved.jsonl"

BACKUP_FILE = METADATA_DIR / "papers_verified_before_title_fix.jsonl"
REVIEW_FILE = METADATA_DIR / "missing_title_review.jsonl"


def load_jsonl(path: Path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                ) + "\n"
            )


def clean_title(title):
    if not title:
        return None

    title = str(title).strip()

    # 파일 확장자 제거
    title = re.sub(
        r"(?i)(?:\.pd)?\.pdf$",
        "",
        title,
    )

    title = re.sub(
        r"(?i)\.pdf$",
        "",
        title,
    )

    # 언더바 → 공백
    title = title.replace("_", " ")

    # 연속 공백
    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip(" .")


def filename_title(filename):
    if not filename:
        return None

    name = Path(filename).name

    # KCI_FI 번호형 파일은 제목으로 사용 금지
    if re.fullmatch(
        r"KCI_FI\d+(?:\.pdf)+",
        name,
        flags=re.I,
    ):
        return None

    # 숫자형 RISS 파일도 사용 금지
    if re.match(
        r"^\d{8,}_",
        name,
    ):
        return None

    title = clean_title(name)

    if not title:
        return None

    # 너무 짧은 것은 제외
    if len(title) < 8:
        return None

    return title


def main():

    verified = load_jsonl(
        VERIFIED_FILE
    )

    ai_rows = load_jsonl(
        AI_FILE
    )

    ai_map = {
        r.get("paper_id"): r
        for r in ai_rows
        if r.get("paper_id")
    }

    # 현재 파일 백업
    write_jsonl(
        BACKUP_FILE,
        verified,
    )

    fixed = 0
    unresolved = []

    print("=" * 72)
    print("제목 누락 문서 보완")
    print("=" * 72)

    for row in verified:

        if row.get("title"):
            continue

        paper_id = row.get("paper_id")
        filename = row.get(
            "source_filename"
        )

        new_title = None
        source = None

        # ----------------------------------------------------
        # 1. AI 결과 내부 다시 확인
        # ----------------------------------------------------

        ai_row = ai_map.get(
            paper_id,
            {},
        )

        ai_metadata = ai_row.get(
            "ai_metadata",
            {},
        )

        if isinstance(ai_metadata, dict):
            candidate = clean_title(
                ai_metadata.get("title")
            )

            if candidate:
                new_title = candidate
                source = "AI_METADATA_RECOVERY"

        # ----------------------------------------------------
        # 2. 파일명이 실제 제목인 경우
        # ----------------------------------------------------

        if not new_title:
            candidate = filename_title(
                filename
            )

            if candidate:
                new_title = candidate
                source = "FILENAME_RECOVERY"

        # ----------------------------------------------------
        # 결과
        # ----------------------------------------------------

        if new_title:

            row["title"] = new_title
            row["title_recovery_source"] = source

            fixed += 1

            print(
                f"[FIX] {paper_id}"
            )
            print(
                f"      {new_title}"
            )
            print(
                f"      SOURCE: {source}"
            )

        else:

            unresolved.append(
                {
                    "paper_id": paper_id,
                    "source_filename": filename,
                    "text_file": row.get(
                        "text_file"
                    ),
                    "document_type": row.get(
                        "document_type"
                    ),
                    "confidence": row.get(
                        "metadata_confidence"
                    ),
                    "ai_metadata": (
                        ai_metadata
                        if isinstance(
                            ai_metadata,
                            dict,
                        )
                        else None
                    ),
                }
            )

            print(
                f"[REVIEW] {paper_id}"
            )
            print(
                f"         {filename}"
            )

    # 수정본 저장
    write_jsonl(
        VERIFIED_FILE,
        verified,
    )

    write_jsonl(
        REVIEW_FILE,
        unresolved,
    )

    remaining = sum(
        1
        for r in verified
        if not r.get("title")
    )

    print()
    print("=" * 72)
    print("제목 보완 완료")
    print("=" * 72)

    print(
        f"보완 성공           : {fixed}"
    )

    print(
        f"아직 제목 없음      : {remaining}"
    )

    print()

    print("수정 파일:")
    print(VERIFIED_FILE)

    print()
    print("백업 파일:")
    print(BACKUP_FILE)

    print()
    print("추가 검토:")
    print(REVIEW_FILE)


if __name__ == "__main__":
    main()