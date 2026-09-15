import json
import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF


PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

PDF_DIR = PROJECT_ROOT / "data" / "pdf"
TEXT_DIR = PROJECT_ROOT / "data" / "text"
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"

REPORT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "pdf_extraction_quality_report.jsonl"
)

SUMMARY_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "pdf_extraction_quality_summary.json"
)


# ------------------------------------------------------------
# 검사 기준
# ------------------------------------------------------------

# 페이지당 cleaned 본문이 이보다 적으면 의심
LOW_CHARS_PER_PAGE = 500

# 전체 cleaned 본문이 이보다 적으면 의심
LOW_CLEANED_CHARS = 3000

# 반복 라인이 너무 많으면 의심
HIGH_REPEATED_LINES = 80

# cleaned 본문 중 한글 비율이 지나치게 낮으면 참고 지표
LOW_KOREAN_RATIO = 0.15


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


def normalize(text):
    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def korean_ratio(text):
    """
    공백을 제외한 문자 중 한글 비율.
    영어 논문/영문 초록도 있으므로 이것만으로 FAIL 처리하지 않는다.
    """

    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    if not compact:
        return 0.0

    korean_chars = len(
        re.findall(
            r"[가-힣]",
            compact,
        )
    )

    return korean_chars / len(compact)


def find_pdf(row, paper_id):
    """
    metadata에 PDF 경로가 있으면 우선 사용하고,
    없으면 data/pdf에서 paper_id 이름을 탐색.
    """

    candidates = [
        row.get("pdf_path"),
        row.get("source_pdf"),
        row.get("pdf_file"),
        row.get("source_file"),
    ]

    for value in candidates:
        if not value:
            continue

        path = Path(value)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        if path.exists() and path.suffix.lower() == ".pdf":
            return path

    direct_candidates = [
        PDF_DIR / f"{paper_id}.pdf",
        PDF_DIR / f"{paper_id.upper()}.pdf",
    ]

    for path in direct_candidates:
        if path.exists():
            return path

    return None


def find_text(row, paper_id):
    candidates = [
        row.get("text_path"),
        row.get("source_text_file"),
    ]

    for value in candidates:
        if not value:
            continue

        path = Path(value)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        if path.exists():
            return path

    path = TEXT_DIR / f"{paper_id}.txt"

    if path.exists():
        return path

    return None


def get_page_count(pdf_path):
    if pdf_path is None:
        return None

    try:
        with fitz.open(pdf_path) as doc:
            return len(doc)

    except Exception:
        return None


def classify(
    page_count,
    raw_chars,
    cleaned_chars,
    chars_per_page,
    repeated_lines,
    ko_ratio,
    preprocess_status,
):
    """
    단일 지표 하나만으로 OCR 대상으로 확정하지 않는다.

    paper_0196처럼 여러 위험 신호가 동시에 나타나는 경우를
    HIGH_RISK로 잡는다.
    """

    signals = []

    if cleaned_chars < LOW_CLEANED_CHARS:
        signals.append(
            "LOW_CLEANED_TEXT"
        )

    if (
        chars_per_page is not None
        and chars_per_page < LOW_CHARS_PER_PAGE
    ):
        signals.append(
            "LOW_TEXT_PER_PAGE"
        )

    if repeated_lines >= HIGH_REPEATED_LINES:
        signals.append(
            "HIGH_REPEATED_LINES"
        )

    if ko_ratio < LOW_KOREAN_RATIO:
        signals.append(
            "LOW_KOREAN_RATIO"
        )

    if preprocess_status == "VERY_SHORT":
        signals.append(
            "PREPROCESS_VERY_SHORT"
        )

    # --------------------------------------------------------
    # 위험도
    # --------------------------------------------------------

    important_signals = {
        "LOW_CLEANED_TEXT",
        "LOW_TEXT_PER_PAGE",
        "HIGH_REPEATED_LINES",
        "PREPROCESS_VERY_SHORT",
    }

    important_count = sum(
        1
        for signal in signals
        if signal in important_signals
    )

    # paper_0196 같은 케이스
    if important_count >= 3:
        status = "HIGH_RISK"

    elif important_count >= 2:
        status = "REVIEW"

    elif important_count == 1:
        status = "CHECK"

    else:
        status = "OK"

    return status, signals


def main():

    rows = load_jsonl(
        METADATA_FILE
    )

    results = []

    status_counter = Counter()

    missing_pdf = []
    missing_text = []
    missing_cleaned = []

    print("=" * 88)
    print("PDF → TXT 추출 품질 전수 검사")
    print("=" * 88)
    print(
        f"검사 대상 : {len(rows)}편"
    )
    print()

    for index, row in enumerate(
        rows,
        start=1,
    ):

        paper_id = row["paper_id"]

        # ----------------------------------------------------
        # 파일 찾기
        # ----------------------------------------------------

        pdf_path = find_pdf(
            row,
            paper_id,
        )

        text_path = find_text(
            row,
            paper_id,
        )

        cleaned_path = (
            CLEANED_DIR
            / f"{paper_id}.json"
        )

        if pdf_path is None:
            missing_pdf.append(
                paper_id
            )

        if text_path is None:
            missing_text.append(
                paper_id
            )

        if not cleaned_path.exists():
            missing_cleaned.append(
                paper_id
            )

            print(
                f"[{index:03d}/{len(rows)}] "
                f"{paper_id} | CLEANED MISSING"
            )

            continue

        # ----------------------------------------------------
        # TXT
        # ----------------------------------------------------

        raw_text = ""

        if text_path is not None:
            raw_text = text_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        raw_chars = len(
            normalize(raw_text)
        )

        # ----------------------------------------------------
        # CLEANED
        # ----------------------------------------------------

        with cleaned_path.open(
            "r",
            encoding="utf-8",
        ) as f:
            cleaned = json.load(f)

        full_text = (
            cleaned.get("full_text")
            or ""
        )

        normalized_cleaned = normalize(
            full_text
        )

        cleaned_chars = len(
            normalized_cleaned
        )

        quality = (
            cleaned.get("quality")
            or {}
        )

        repeated_lines = quality.get(
            "removed_repeated_lines",
            0,
        ) or 0

        preprocess_status = quality.get(
            "status"
        )

        # ----------------------------------------------------
        # PDF 페이지 수
        # ----------------------------------------------------

        page_count = get_page_count(
            pdf_path
        )

        if (
            page_count is not None
            and page_count > 0
        ):
            chars_per_page = (
                cleaned_chars
                / page_count
            )

        else:
            chars_per_page = None

        # ----------------------------------------------------
        # 한글 비율
        # ----------------------------------------------------

        ko_ratio = korean_ratio(
            normalized_cleaned
        )

        # ----------------------------------------------------
        # 판정
        # ----------------------------------------------------

        status, signals = classify(
            page_count=page_count,
            raw_chars=raw_chars,
            cleaned_chars=cleaned_chars,
            chars_per_page=chars_per_page,
            repeated_lines=repeated_lines,
            ko_ratio=ko_ratio,
            preprocess_status=preprocess_status,
        )

        status_counter[
            status
        ] += 1

        result = {
            "paper_id":
                paper_id,

            "title":
                row.get("title"),

            "pdf_path":
                str(pdf_path)
                if pdf_path
                else None,

            "text_path":
                str(text_path)
                if text_path
                else None,

            "page_count":
                page_count,

            "raw_text_chars":
                raw_chars,

            "cleaned_chars":
                cleaned_chars,

            "cleaned_chars_per_page":
                round(
                    chars_per_page,
                    2,
                )
                if chars_per_page
                is not None
                else None,

            "korean_ratio_percent":
                round(
                    ko_ratio * 100,
                    2,
                ),

            "removed_repeated_lines":
                repeated_lines,

            "preprocess_status":
                preprocess_status,

            "text_source":
                quality.get(
                    "text_source"
                ),

            "status":
                status,

            "signals":
                signals,
        }

        results.append(
            result
        )

        cpp_text = (
            f"{chars_per_page:7.1f}"
            if chars_per_page is not None
            else "   N/A "
        )

        page_text = (
            str(page_count)
            if page_count is not None
            else "?"
        )

        print(
            f"[{index:03d}/{len(rows)}] "
            f"{paper_id} | "
            f"{status:<9} | "
            f"pages {page_text:>3} | "
            f"clean {cleaned_chars:>7,} | "
            f"/page {cpp_text} | "
            f"repeat {repeated_lines:>4}"
        )

    # --------------------------------------------------------
    # 상세 결과 저장
    # --------------------------------------------------------

    with REPORT_FILE.open(
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

    # --------------------------------------------------------
    # 위험 문서 정렬
    # --------------------------------------------------------

    priority = {
        "HIGH_RISK": 0,
        "REVIEW": 1,
        "CHECK": 2,
        "OK": 3,
    }

    suspicious = sorted(
        [
            row
            for row in results
            if row["status"] != "OK"
        ],
        key=lambda row: (
            priority.get(
                row["status"],
                99,
            ),
            row[
                "cleaned_chars_per_page"
            ]
            if row[
                "cleaned_chars_per_page"
            ] is not None
            else 999999,
        ),
    )

    summary = {
        "total_expected":
            len(rows),

        "total_checked":
            len(results),

        "missing_pdf_count":
            len(missing_pdf),

        "missing_pdf":
            missing_pdf,

        "missing_text_count":
            len(missing_text),

        "missing_text":
            missing_text,

        "missing_cleaned_count":
            len(missing_cleaned),

        "missing_cleaned":
            missing_cleaned,

        "status_counts":
            dict(
                status_counter
            ),

        "high_risk_count":
            status_counter.get(
                "HIGH_RISK",
                0,
            ),

        "review_count":
            status_counter.get(
                "REVIEW",
                0,
            ),

        "check_count":
            status_counter.get(
                "CHECK",
                0,
            ),

        "suspicious_papers":
            suspicious,
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # 최종 출력
    # --------------------------------------------------------

    print()
    print("=" * 88)
    print("PDF → TXT 추출 품질 검사 완료")
    print("=" * 88)

    print(
        f"검사 대상             : {len(rows)}"
    )

    print(
        f"검사 완료             : {len(results)}"
    )

    print(
        f"PDF 경로 확인 실패    : {len(missing_pdf)}"
    )

    print(
        f"TXT 없음              : {len(missing_text)}"
    )

    print(
        f"Cleaned 없음          : {len(missing_cleaned)}"
    )

    print()
    print("[판정]")

    for status in [
        "OK",
        "CHECK",
        "REVIEW",
        "HIGH_RISK",
    ]:

        print(
            f"{status:<20}: "
            f"{status_counter.get(status, 0)}"
        )

    print()
    print(
        f"검토 대상 총합        : "
        f"{len(suspicious)}"
    )

    if suspicious:

        print()
        print(
            "[검토 우선순위 - 최대 30편]"
        )

        for row in suspicious[:30]:

            cpp = row[
                "cleaned_chars_per_page"
            ]

            cpp_text = (
                f"{cpp:.1f}"
                if cpp is not None
                else "N/A"
            )

            print()
            print(
                f"{row['paper_id']} | "
                f"{row['status']}"
            )

            print(
                f"  제목      : "
                f"{row['title']}"
            )

            print(
                f"  페이지    : "
                f"{row['page_count']}"
            )

            print(
                f"  TXT       : "
                f"{row['raw_text_chars']:,}자"
            )

            print(
                f"  Cleaned   : "
                f"{row['cleaned_chars']:,}자"
            )

            print(
                f"  페이지당  : "
                f"{cpp_text}자"
            )

            print(
                f"  반복제거  : "
                f"{row['removed_repeated_lines']}줄"
            )

            print(
                f"  한글비율  : "
                f"{row['korean_ratio_percent']}%"
            )

            print(
                f"  신호      : "
                f"{', '.join(row['signals'])}"
            )

    print()
    print("상세 결과:")
    print(REPORT_FILE)

    print()
    print("요약:")
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()