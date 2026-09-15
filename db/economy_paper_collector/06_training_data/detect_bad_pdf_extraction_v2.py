import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PREPROCESSED_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "papers_preprocessed.jsonl"
)

EXTRACTED_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "papers_extracted.jsonl"
)

CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"

REPORT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "pdf_extraction_quality_report_v2.jsonl"
)

SUMMARY_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "pdf_extraction_quality_summary_v2.json"
)


def load_jsonl(path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def normalize(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def korean_ratio(text):
    compact = re.sub(r"\s+", "", text)

    if not compact:
        return 0.0

    korean = len(
        re.findall(r"[가-힣]", compact)
    )

    return korean / len(compact)


def main():

    preprocessed = load_jsonl(
        PREPROCESSED_FILE
    )

    extracted = load_jsonl(
        EXTRACTED_FILE
    )

    # paper_id → 최초 PDF 추출 정보
    extracted_map = {
        row["paper_id"]: row
        for row in extracted
    }

    results = []
    counts = Counter()

    print("=" * 90)
    print("PDF → TXT 실질 본문 품질 검사 V2")
    print("=" * 90)
    print(f"검사 대상 : {len(preprocessed)}편")
    print()

    for row in preprocessed:

        paper_id = row["paper_id"]

        extraction = extracted_map.get(
            paper_id
        )

        cleaned_path = (
            CLEANED_DIR
            / f"{paper_id}.json"
        )

        if extraction is None:
            print(
                f"{paper_id} | "
                f"EXTRACTION METADATA MISSING"
            )
            continue

        if not cleaned_path.exists():
            print(
                f"{paper_id} | "
                f"CLEANED MISSING"
            )
            continue

        with cleaned_path.open(
            "r",
            encoding="utf-8",
        ) as f:
            cleaned = json.load(f)

        quality = (
            cleaned.get("quality")
            or {}
        )

        full_text = normalize(
            cleaned.get("full_text", "")
        )

        page_count = (
            extraction.get("page_count")
            or 0
        )

        extracted_chars = (
            extraction.get("text_chars")
            or 0
        )

        cleaned_chars = len(full_text)

        repeated_lines = (
            quality.get(
                "removed_repeated_lines",
                0,
            )
            or 0
        )

        preprocess_status = (
            quality.get("status")
        )

        text_source = (
            quality.get("text_source")
        )

        ko_ratio = korean_ratio(
            full_text
        )

        if page_count > 0:
            extracted_per_page = (
                extracted_chars / page_count
            )

            cleaned_per_page = (
                cleaned_chars / page_count
            )
        else:
            extracted_per_page = 0
            cleaned_per_page = 0

        # ---------------------------------------------
        # 위험 신호
        # ---------------------------------------------

        signals = []

        # 실제 정제 본문이 매우 적음
        if cleaned_chars < 3000:
            signals.append(
                "VERY_LOW_CLEANED_TEXT"
            )

        # 페이지당 실질 본문량
        if (
            page_count >= 5
            and cleaned_per_page < 250
        ):
            signals.append(
                "VERY_LOW_TEXT_PER_PAGE"
            )

        elif (
            page_count >= 5
            and cleaned_per_page < 500
        ):
            signals.append(
                "LOW_TEXT_PER_PAGE"
            )

        # 최초 추출 자체도 빈약
        if (
            page_count >= 5
            and extracted_per_page < 350
        ):
            signals.append(
                "LOW_RAW_EXTRACTION_PER_PAGE"
            )

        # 반복 워터마크/헤더가 과도함
        if repeated_lines >= 80:
            signals.append(
                "HIGH_REPEATED_LINES"
            )

        if preprocess_status == "VERY_SHORT":
            signals.append(
                "PREPROCESS_VERY_SHORT"
            )

        # 한글 논문일 가능성이 높은데
        # 한글 비율이 지나치게 낮은 경우는 참고
        if ko_ratio < 0.05:
            signals.append(
                "VERY_LOW_KOREAN_RATIO"
            )

        # ---------------------------------------------
        # 판정
        # ---------------------------------------------

        severe = {
            "VERY_LOW_CLEANED_TEXT",
            "VERY_LOW_TEXT_PER_PAGE",
            "LOW_RAW_EXTRACTION_PER_PAGE",
            "PREPROCESS_VERY_SHORT",
        }

        severe_count = sum(
            1
            for signal in signals
            if signal in severe
        )

        if (
            "VERY_LOW_TEXT_PER_PAGE" in signals
            and severe_count >= 2
        ):
            status = "OCR_CANDIDATE"

        elif severe_count >= 2:
            status = "REVIEW"

        elif severe_count == 1:
            status = "CHECK"

        else:
            status = "OK"

        counts[status] += 1

        result = {
            "paper_id": paper_id,
            "title": row.get("title"),

            "source_filename":
                extraction.get(
                    "source_filename"
                ),

            "page_count":
                page_count,

            "original_extracted_chars":
                extracted_chars,

            "cleaned_chars":
                cleaned_chars,

            "extracted_chars_per_page":
                round(
                    extracted_per_page,
                    2,
                ),

            "cleaned_chars_per_page":
                round(
                    cleaned_per_page,
                    2,
                ),

            "removed_repeated_lines":
                repeated_lines,

            "korean_ratio_percent":
                round(
                    ko_ratio * 100,
                    2,
                ),

            "preprocess_status":
                preprocess_status,

            "text_source":
                text_source,

            "status":
                status,

            "signals":
                signals,
        }

        results.append(result)

    # ---------------------------------------------
    # 저장
    # ---------------------------------------------

    with REPORT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for row in results:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

    priority = {
        "OCR_CANDIDATE": 0,
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
        key=lambda x: (
            priority[x["status"]],
            x["cleaned_chars_per_page"],
        ),
    )

    summary = {
        "total": len(results),
        "status_counts": dict(counts),
        "suspicious_count":
            len(suspicious),
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

    # ---------------------------------------------
    # 출력
    # ---------------------------------------------

    print("=" * 90)
    print("최종 검사 결과")
    print("=" * 90)

    print(
        f"전체 검사       : {len(results)}"
    )

    print()

    for status in [
        "OK",
        "CHECK",
        "REVIEW",
        "OCR_CANDIDATE",
    ]:

        print(
            f"{status:<20}: "
            f"{counts.get(status, 0)}"
        )

    print()
    print(
        f"검토 대상       : "
        f"{len(suspicious)}"
    )

    print()
    print("=" * 90)
    print("검토 우선 문서")
    print("=" * 90)

    for row in suspicious[:30]:

        print()

        print(
            f"{row['paper_id']} | "
            f"{row['status']}"
        )

        print(
            f"  제목       : "
            f"{row['title']}"
        )

        print(
            f"  원본 PDF   : "
            f"{row['source_filename']}"
        )

        print(
            f"  페이지     : "
            f"{row['page_count']}"
        )

        print(
            f"  최초추출   : "
            f"{row['original_extracted_chars']:,}자 "
            f"({row['extracted_chars_per_page']:.1f}/page)"
        )

        print(
            f"  Cleaned    : "
            f"{row['cleaned_chars']:,}자 "
            f"({row['cleaned_chars_per_page']:.1f}/page)"
        )

        print(
            f"  반복제거   : "
            f"{row['removed_repeated_lines']}줄"
        )

        print(
            f"  추출방식   : "
            f"{row['text_source']}"
        )

        print(
            f"  신호       : "
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