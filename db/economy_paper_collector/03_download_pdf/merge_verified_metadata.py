from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

RESOLVED_FILE = METADATA_DIR / "papers_resolved.jsonl"
AI_FILE = METADATA_DIR / "papers_ai_resolved.jsonl"
HIGH_FILE = METADATA_DIR / "papers_high_completed.jsonl"

OUTPUT_FILE = METADATA_DIR / "papers_verified.jsonl"
REVIEW_FILE = METADATA_DIR / "papers_verified_review.jsonl"


# ============================================================
# JSONL
# ============================================================

def load_jsonl(path: Path) -> list[dict]:
    rows = []

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))

            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"{path.name} "
                    f"{line_no}번째 줄 JSON 오류: {e}"
                )

    return rows


def write_jsonl(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


# ============================================================
# 기본 정리
# ============================================================

def clean_string(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() in {
        "null",
        "none",
        "unknown",
        "n/a",
    }:
        return None

    return value


def clean_title(value):
    value = clean_string(value)

    if not value:
        return None

    value = value.replace("\r", " ")
    value = value.replace("\n", " ")

    # 연속 공백만 정리
    value = re.sub(r"\s+", " ", value)

    # 콜론 주변 정리
    value = re.sub(
        r"\s*:\s*",
        ": ",
        value,
    )

    # 괄호 주변 불필요 공백
    value = re.sub(r"\(\s+", "(", value)
    value = re.sub(r"\s+\)", ")", value)

    return value.strip()


def normalize_authors(value):
    if value is None:
        return []

    if isinstance(value, list):
        result = []

        for author in value:
            author = clean_string(author)

            if (
                author
                and author not in result
            ):
                result.append(author)

        return result

    value = clean_string(value)

    if not value:
        return []

    parts = re.split(
        r"\s*(?:,|;|\||·)\s*",
        value,
    )

    return [
        p.strip()
        for p in parts
        if p.strip()
    ]


def normalize_year(value):
    if value is None:
        return None

    match = re.search(
        r"(?:19|20)\d{2}",
        str(value),
    )

    if not match:
        return None

    year = int(match.group())

    if 1900 <= year <= 2030:
        return year

    return None


def normalize_doi(value):
    value = clean_string(value)

    if not value:
        return None

    value = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"^doi\s*:\s*",
        "",
        value,
        flags=re.I,
    )

    return value.strip()


def normalize_confidence(value):
    value = clean_string(value)

    if not value:
        return "LOW"

    value = value.upper()

    # AI_HIGH 같은 값도 대응
    if value.startswith("AI_"):
        value = value[3:]

    if value in {
        "HIGH",
        "MEDIUM",
        "LOW",
    }:
        return value

    return "LOW"


def normalize_document_type(value):
    value = clean_string(value)

    if not value:
        return None

    value = value.lower().strip()

    aliases = {
        "article": "journal_article",
        "journal": "journal_article",
        "journal article": "journal_article",

        "master": "master_thesis",
        "master's thesis": "master_thesis",

        "doctoral": "doctoral_thesis",
        "phd": "doctoral_thesis",
        "phd_thesis": "doctoral_thesis",

        # 너무 모호하므로 별도 유지하지 않고
        # thesis로 남겨 후속 검토
        "thesis": "thesis",
    }

    return aliases.get(
        value,
        value,
    )


# ============================================================
# 값 선택
# ============================================================

def choose(
    primary: dict,
    base: dict,
    key: str,
):
    """
    primary = AI/보충 결과
    base    = 기존 deterministic 결과

    primary 값이 있으면 우선 사용.
    없으면 base 값 사용.
    """

    value = primary.get(key)

    if value not in (
        None,
        "",
        [],
        {},
    ):
        return value

    return base.get(key)


# ============================================================
# canonical record
# ============================================================

def build_record(
    base: dict,
    metadata: dict,
    source: str,
):
    title = clean_title(
        choose(
            metadata,
            base,
            "title",
        )
    )

    authors = normalize_authors(
        choose(
            metadata,
            base,
            "authors",
        )
    )

    year = normalize_year(
        choose(
            metadata,
            base,
            "year",
        )
    )

    journal = clean_string(
        choose(
            metadata,
            base,
            "journal",
        )
    )

    institution = clean_string(
        choose(
            metadata,
            base,
            "institution",
        )
    )

    department = clean_string(
        choose(
            metadata,
            base,
            "department",
        )
    )

    document_type = normalize_document_type(
        choose(
            metadata,
            base,
            "document_type",
        )
    )

    doi = normalize_doi(
        choose(
            metadata,
            base,
            "doi",
        )
    )

    # confidence는 metadata 쪽 판정을 사용
    confidence = normalize_confidence(
        metadata.get("confidence")
        or metadata.get("metadata_status")
    )

    record = {
        "paper_id": base.get("paper_id"),

        "title": title,
        "authors": authors,
        "year": year,

        "journal": journal,
        "institution": institution,
        "department": department,

        "document_type": document_type,

        "doi": doi,
        "kci_id": clean_string(
            base.get("kci_id")
        ),

        "source_filename": (
            base.get("source_filename")
        ),

        "text_file": (
            base.get("text_file")
        ),

        "sha256": (
            base.get("sha256")
        ),

        "page_count": (
            base.get("page_count")
        ),

        "text_chars": (
            base.get("text_chars")
        ),

        "metadata_confidence": confidence,
        "metadata_source": source,

        "evidence": clean_string(
            metadata.get("evidence")
        ),
    }

    return record


# ============================================================
# 검토 사유
# ============================================================

def get_review_reasons(row):
    reasons = []

    if not row.get("title"):
        reasons.append(
            "MISSING_TITLE"
        )

    if not row.get("authors"):
        reasons.append(
            "MISSING_AUTHORS"
        )

    if not row.get("year"):
        reasons.append(
            "MISSING_YEAR"
        )

    if not row.get("document_type"):
        reasons.append(
            "MISSING_DOCUMENT_TYPE"
        )

    confidence = row.get(
        "metadata_confidence"
    )

    if confidence == "MEDIUM":
        reasons.append(
            "MEDIUM_CONFIDENCE"
        )

    elif confidence == "LOW":
        reasons.append(
            "LOW_CONFIDENCE"
        )

    if row.get("document_type") in {
        "report",
        "policy_document",
        "news",
        "other",
        "thesis",
    }:
        reasons.append(
            "DOCUMENT_TYPE_REVIEW"
        )

    return reasons


# ============================================================
# main
# ============================================================

def main():

    print("=" * 72)
    print("216개 논문 메타데이터 최종 통합")
    print("=" * 72)

    resolved_rows = load_jsonl(
        RESOLVED_FILE
    )

    ai_rows = load_jsonl(
        AI_FILE
    )

    high_rows = load_jsonl(
        HIGH_FILE
    )

    print(
        f"기존 전체            : {len(resolved_rows)}"
    )

    print(
        f"AI REVIEW 처리       : {len(ai_rows)}"
    )

    print(
        f"기존 HIGH 보충       : {len(high_rows)}"
    )

    # --------------------------------------------------------
    # map
    # --------------------------------------------------------

    base_map = {
        row["paper_id"]: row
        for row in resolved_rows
        if row.get("paper_id")
    }

    ai_map = {
        row["paper_id"]: row
        for row in ai_rows
        if row.get("paper_id")
    }

    high_map = {
        row["paper_id"]: row
        for row in high_rows
        if row.get("paper_id")
    }

    # --------------------------------------------------------
    # 구조 검증
    # --------------------------------------------------------

    ai_with_metadata = sum(
        1
        for row in ai_rows
        if isinstance(
            row.get("ai_metadata"),
            dict,
        )
    )

    print(
        f"ai_metadata 확인      : "
        f"{ai_with_metadata}/{len(ai_rows)}"
    )

    if ai_with_metadata != len(ai_rows):
        print()
        print(
            "[경고] 일부 AI 레코드에 "
            "ai_metadata가 없습니다."
        )

    # --------------------------------------------------------
    # overlap 검사
    # --------------------------------------------------------

    overlap = (
        set(ai_map)
        & set(high_map)
    )

    print(
        f"AI/HIGH ID 중복       : {len(overlap)}"
    )

    # 정상은 0
    if overlap:
        for paper_id in sorted(overlap):
            print(
                "  -",
                paper_id,
            )

    # --------------------------------------------------------
    # 통합
    # --------------------------------------------------------

    merged = []
    unresolved_ids = []

    for paper_id in sorted(base_map):

        base = base_map[paper_id]

        # 기존 deterministic HIGH 42개
        if paper_id in high_map:

            metadata = high_map[
                paper_id
            ]

            record = build_record(
                base=base,
                metadata=metadata,
                source=(
                    "DETERMINISTIC_HIGH"
                    "+AI_COMPLETION"
                ),
            )

        # 기존 REVIEW 174개
        elif paper_id in ai_map:

            ai_row = ai_map[
                paper_id
            ]

            # ★ 핵심 수정 부분
            metadata = ai_row.get(
                "ai_metadata"
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            record = build_record(
                base=base,
                metadata=metadata,
                source=(
                    "AI_REVIEW_RESOLUTION"
                ),
            )

        else:

            unresolved_ids.append(
                paper_id
            )

            record = build_record(
                base=base,
                metadata={},
                source="UNRESOLVED",
            )

        merged.append(record)

    # --------------------------------------------------------
    # 검토 대상
    # --------------------------------------------------------

    review_rows = []

    for row in merged:

        reasons = get_review_reasons(
            row
        )

        if reasons:
            review = dict(row)

            review[
                "review_reasons"
            ] = reasons

            review_rows.append(
                review
            )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_FILE,
        merged,
    )

    write_jsonl(
        REVIEW_FILE,
        review_rows,
    )

    # --------------------------------------------------------
    # 통계
    # --------------------------------------------------------

    confidence_counts = Counter(
        row["metadata_confidence"]
        for row in merged
    )

    type_counts = Counter(
        row.get("document_type")
        or "UNKNOWN"
        for row in merged
    )

    missing_title = sum(
        not row.get("title")
        for row in merged
    )

    missing_authors = sum(
        not row.get("authors")
        for row in merged
    )

    missing_year = sum(
        not row.get("year")
        for row in merged
    )

    missing_type = sum(
        not row.get("document_type")
        for row in merged
    )

    # --------------------------------------------------------
    # 결과
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("최종 통합 완료")
    print("=" * 72)

    print(
        f"최종 레코드          : {len(merged)}"
    )

    print(
        f"메타데이터 누락 ID   : {len(unresolved_ids)}"
    )

    print()

    print("[Confidence]")

    for key in [
        "HIGH",
        "MEDIUM",
        "LOW",
    ]:
        print(
            f"{key:<18}: "
            f"{confidence_counts.get(key, 0)}"
        )

    print()
    print("[Document Type]")

    for key, count in (
        type_counts.most_common()
    ):
        print(
            f"{key:<22}: {count}"
        )

    print()
    print("[필수 메타데이터 누락]")

    print(
        f"제목 없음            : {missing_title}"
    )

    print(
        f"저자 없음            : {missing_authors}"
    )

    print(
        f"연도 없음            : {missing_year}"
    )

    print(
        f"문서유형 없음        : {missing_type}"
    )

    print()

    print(
        f"검토 대상            : {len(review_rows)}"
    )

    print()

    print("최종 통합 파일:")
    print(OUTPUT_FILE)

    print()
    print("검토 파일:")
    print(REVIEW_FILE)


if __name__ == "__main__":
    main()