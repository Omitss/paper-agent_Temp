import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "content_preservation_report.jsonl"
)

SUMMARY_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "content_preservation_summary.json"
)


# ============================================================
# 기준
# ============================================================

# cleaned/full_text가 원본 TXT의 몇 %인지
CLEANED_WARNING_RATIO = 0.60
CLEANED_CRITICAL_RATIO = 0.35

# section content 합계가 cleaned/full_text의 몇 %인지
SECTION_WARNING_RATIO = 0.60
SECTION_CRITICAL_RATIO = 0.35


def load_jsonl(path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(
                    json.loads(line)
                )

    return rows


def normalize_for_count(text):
    """
    페이지 구분자와 불필요한 공백 차이 때문에
    길이가 과도하게 달라 보이는 것을 줄이기 위한 비교용 정규화.
    """

    if not text:
        return ""

    text = re.sub(
        r"={3,}\s*PAGE\s+\d+\s*={3,}",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def safe_ratio(a, b):
    if b <= 0:
        return 0.0

    return a / b


def get_original_text_path(row, paper_id):

    # 전처리 때 실제 사용한 source가 기록돼 있다면 우선 사용
    source = row.get(
        "preprocess_source_file"
    )

    if source:
        path = Path(source)

        if path.exists():
            return path

    # OCR recovered
    ocr_path = (
        PROJECT_ROOT
        / "data"
        / "text_ocr_recovered"
        / f"{paper_id}.txt"
    )

    if ocr_path.exists():
        return ocr_path

    # 일반 PyMuPDF TXT
    normal_path = (
        PROJECT_ROOT
        / "data"
        / "text"
        / f"{paper_id}.txt"
    )

    if normal_path.exists():
        return normal_path

    return None


def get_cleaned_path(row, paper_id):

    path_value = row.get(
        "cleaned_file"
    )

    if path_value:
        path = Path(path_value)

        if path.exists():
            return path

    fallback = (
        PROJECT_ROOT
        / "data"
        / "cleaned"
        / f"{paper_id}.json"
    )

    if fallback.exists():
        return fallback

    return None


def classify(
    raw_chars,
    cleaned_chars,
    section_chars,
    cleaned_ratio,
    section_ratio,
):

    reasons = []

    # 원본 자체가 매우 짧은 경우
    if raw_chars < 3000:
        reasons.append(
            "SOURCE_TEXT_SHORT"
        )

    # cleaned 보존율
    if cleaned_ratio < CLEANED_CRITICAL_RATIO:
        reasons.append(
            "CRITICAL_CLEANED_LOSS"
        )

    elif cleaned_ratio < CLEANED_WARNING_RATIO:
        reasons.append(
            "WARNING_CLEANED_LOSS"
        )

    # section 보존율
    if cleaned_chars > 0:

        if section_ratio < SECTION_CRITICAL_RATIO:
            reasons.append(
                "CRITICAL_SECTION_LOSS"
            )

        elif section_ratio < SECTION_WARNING_RATIO:
            reasons.append(
                "WARNING_SECTION_LOSS"
            )

    if any(
        reason.startswith("CRITICAL")
        for reason in reasons
    ):
        status = "CRITICAL"

    elif any(
        reason.startswith("WARNING")
        for reason in reasons
    ):
        status = "WARNING"

    elif "SOURCE_TEXT_SHORT" in reasons:
        status = "SOURCE_SHORT"

    else:
        status = "OK"

    return status, reasons


def main():

    rows = load_jsonl(
        METADATA_FILE
    )

    results = []

    status_counter = Counter()

    missing_source = []
    missing_cleaned = []

    print("=" * 78)
    print("논문 본문 보존율 전수 검사")
    print("=" * 78)
    print(f"검사 대상 : {len(rows)}편")
    print()

    for index, row in enumerate(
        rows,
        start=1,
    ):

        paper_id = row["paper_id"]

        source_path = get_original_text_path(
            row,
            paper_id,
        )

        cleaned_path = get_cleaned_path(
            row,
            paper_id,
        )

        if source_path is None:
            missing_source.append(
                paper_id
            )

            print(
                f"[{index:03d}/{len(rows)}] "
                f"{paper_id} | SOURCE MISSING"
            )

            continue

        if cleaned_path is None:
            missing_cleaned.append(
                paper_id
            )

            print(
                f"[{index:03d}/{len(rows)}] "
                f"{paper_id} | CLEANED MISSING"
            )

            continue

        raw_text = source_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        with cleaned_path.open(
            "r",
            encoding="utf-8",
        ) as f:
            cleaned = json.load(f)

        full_text = (
            cleaned.get("full_text")
            or ""
        )

        sections = (
            cleaned.get("sections")
            or []
        )

        # 비교용 길이
        raw_normalized = normalize_for_count(
            raw_text
        )

        cleaned_normalized = normalize_for_count(
            full_text
        )

        section_texts = []

        for section in sections:

            content = (
                section.get("content")
                or ""
            )

            if content.strip():
                section_texts.append(
                    content
                )

        section_combined = normalize_for_count(
            "\n".join(section_texts)
        )

        raw_chars = len(
            raw_normalized
        )

        cleaned_chars = len(
            cleaned_normalized
        )

        section_chars = len(
            section_combined
        )

        cleaned_ratio = safe_ratio(
            cleaned_chars,
            raw_chars,
        )

        section_ratio = safe_ratio(
            section_chars,
            cleaned_chars,
        )

        status, reasons = classify(
            raw_chars,
            cleaned_chars,
            section_chars,
            cleaned_ratio,
            section_ratio,
        )

        status_counter[
            status
        ] += 1

        result = {
            "paper_id":
                paper_id,

            "title":
                row.get("title"),

            "preprocess_status":
                row.get(
                    "preprocess_status"
                ),

            "text_source":
                row.get(
                    "text_source"
                ),

            "source_file":
                str(source_path),

            "cleaned_file":
                str(cleaned_path),

            "source_chars":
                raw_chars,

            "cleaned_chars":
                cleaned_chars,

            "section_chars":
                section_chars,

            "cleaned_preservation_ratio":
                round(
                    cleaned_ratio,
                    4,
                ),

            "cleaned_preservation_percent":
                round(
                    cleaned_ratio * 100,
                    2,
                ),

            "section_coverage_ratio":
                round(
                    section_ratio,
                    4,
                ),

            "section_coverage_percent":
                round(
                    section_ratio * 100,
                    2,
                ),

            "status":
                status,

            "reasons":
                reasons,
        }

        results.append(
            result
        )

        print(
            f"[{index:03d}/{len(rows)}] "
            f"{paper_id} | "
            f"{status:<12} | "
            f"TXT {raw_chars:>8,} | "
            f"CLEAN {cleaned_chars:>8,} "
            f"({cleaned_ratio * 100:>6.1f}%) | "
            f"SECTION {section_chars:>8,} "
            f"({section_ratio * 100:>6.1f}%)"
        )

    # ========================================================
    # 저장
    # ========================================================

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for result in results:

            f.write(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
                + "\n"
            )

    # 가장 위험한 문서
    suspicious = sorted(
        [
            row
            for row in results
            if row["status"]
            in {
                "WARNING",
                "CRITICAL",
                "SOURCE_SHORT",
            }
        ],
        key=lambda x: (
            x[
                "cleaned_preservation_ratio"
            ],
            x[
                "section_coverage_ratio"
            ],
        ),
    )

    # 전체 통계
    if results:

        avg_cleaned_ratio = (
            sum(
                row[
                    "cleaned_preservation_ratio"
                ]
                for row in results
            )
            / len(results)
        )

        avg_section_ratio = (
            sum(
                row[
                    "section_coverage_ratio"
                ]
                for row in results
            )
            / len(results)
        )

    else:
        avg_cleaned_ratio = 0
        avg_section_ratio = 0

    summary = {
        "total_expected":
            len(rows),

        "total_checked":
            len(results),

        "missing_source":
            missing_source,

        "missing_cleaned":
            missing_cleaned,

        "status_counts":
            dict(
                status_counter
            ),

        "average_cleaned_preservation_percent":
            round(
                avg_cleaned_ratio * 100,
                2,
            ),

        "average_section_coverage_percent":
            round(
                avg_section_ratio * 100,
                2,
            ),

        "suspicious_count":
            len(suspicious),

        "suspicious_papers":
            [
                {
                    "paper_id":
                        row["paper_id"],

                    "title":
                        row["title"],

                    "status":
                        row["status"],

                    "source_chars":
                        row["source_chars"],

                    "cleaned_chars":
                        row["cleaned_chars"],

                    "section_chars":
                        row["section_chars"],

                    "cleaned_percent":
                        row[
                            "cleaned_preservation_percent"
                        ],

                    "section_percent":
                        row[
                            "section_coverage_percent"
                        ],

                    "reasons":
                        row["reasons"],
                }
                for row in suspicious
            ],
        }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # 최종 출력
    # ========================================================

    print()
    print("=" * 78)
    print("본문 보존율 검사 완료")
    print("=" * 78)

    print(
        f"검사 대상              : {len(rows)}"
    )

    print(
        f"정상 검사              : {len(results)}"
    )

    print(
        f"원본 TXT 없음          : {len(missing_source)}"
    )

    print(
        f"Cleaned JSON 없음      : {len(missing_cleaned)}"
    )

    print()
    print("[상태]")

    for key in [
        "OK",
        "WARNING",
        "CRITICAL",
        "SOURCE_SHORT",
    ]:

        print(
            f"{key:<20}: "
            f"{status_counter.get(key, 0)}"
        )

    print()

    print(
        "평균 TXT → Cleaned 보존율 : "
        f"{avg_cleaned_ratio * 100:.2f}%"
    )

    print(
        "평균 Cleaned → Section 범위: "
        f"{avg_section_ratio * 100:.2f}%"
    )

    print()
    print(
        f"검토 대상              : {len(suspicious)}"
    )

    # 위험 문서 상위 20개
    if suspicious:

        print()
        print("[검토 우선 문서 - 최대 20개]")

        for row in suspicious[:20]:

            print(
                f"{row['paper_id']} | "
                f"{row['status']:<12} | "
                f"TXT→Clean "
                f"{row['cleaned_preservation_percent']:>6.1f}% | "
                f"Clean→Section "
                f"{row['section_coverage_percent']:>6.1f}% | "
                f"{row['title']}"
            )

    print()
    print("상세 결과:")
    print(OUTPUT_FILE)

    print()
    print("요약:")
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()