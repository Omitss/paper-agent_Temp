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

CLEANED_DIR = (
    PROJECT_ROOT
    / "data"
    / "cleaned"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "section_failure_analysis.json"
)


TARGET_STATUSES = {
    "SECTION_FAILED",
    "LOW_SECTION_DETECTION",
}


# ------------------------------------------------------------
# JSONL
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 제목처럼 보이는 줄 찾기
# ------------------------------------------------------------

def is_heading_candidate(line):

    line = line.strip()

    if not line:
        return False

    # 너무 긴 문장은 제외
    if len(line) > 100:
        return False

    # 너무 짧은 숫자/기호 제외
    if re.fullmatch(
        r"[\d\s\-–—·.]+",
        line,
    ):
        return False

    patterns = [

        # Ⅰ. 서론 / Ⅱ. 이론적 배경
        r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[\.\s]",

        # I. 서론 / II. 연구방법
        r"^[IVX]{1,8}[\.\s]",

        # 1. 서론 / 2. 이론적 배경
        r"^\d{1,2}\s*[\.\)]\s*\S+",

        # 제1장 / 제 2 장
        r"^제\s*\d+\s*장",

        # 1장 / 2장
        r"^\d+\s*장",

        # 1) 연구배경
        r"^\d{1,2}\s*\)\s*\S+",

        # 가. / 나.
        r"^[가-힣]\s*[\.\)]\s*\S+",

        # 직접적인 주요 섹션명
        (
            r"^(?:"
            r"서\s*론|"
            r"연구\s*배경|"
            r"이론적\s*배경|"
            r"이론적\s*고찰|"
            r"선행\s*연구|"
            r"문헌\s*연구|"
            r"문헌\s*고찰|"
            r"관련\s*연구|"
            r"연구\s*방법|"
            r"연구\s*설계|"
            r"연구\s*모형|"
            r"분석\s*방법|"
            r"연구\s*결과|"
            r"분석\s*결과|"
            r"실증\s*분석|"
            r"논\s*의|"
            r"고\s*찰|"
            r"결\s*론|"
            r"결론\s*및.*|"
            r"요약\s*및\s*결론|"
            r"참고\s*문헌|"
            r"References"
            r")$"
        ),
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            line,
            re.I,
        ):
            return True

    return False


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    rows = load_jsonl(
        METADATA_FILE
    )

    targets = [
        row
        for row in rows
        if row.get("preprocess_status")
        in TARGET_STATUSES
    ]

    print("=" * 72)
    print("섹션 탐지 실패 분석")
    print("=" * 72)

    print(
        f"전체 전처리 논문      : {len(rows)}"
    )

    print(
        f"분석 대상            : {len(targets)}"
    )

    heading_counter = Counter()

    results = []

    for index, row in enumerate(
        targets,
        start=1,
    ):

        paper_id = row["paper_id"]

        cleaned_file = (
            CLEANED_DIR
            / f"{paper_id}.json"
        )

        if not cleaned_file.exists():
            continue

        data = json.loads(
            cleaned_file.read_text(
                encoding="utf-8"
            )
        )

        text = data.get(
            "full_text",
            "",
        )

        candidates = []

        for line in text.splitlines():

            line = re.sub(
                r"\s+",
                " ",
                line.strip(),
            )

            if is_heading_candidate(
                line
            ):

                candidates.append(
                    line
                )

                heading_counter[
                    line
                ] += 1

        # 중복 제목 제거, 순서 유지
        unique_candidates = list(
            dict.fromkeys(
                candidates
            )
        )

        result = {
            "paper_id": paper_id,
            "title": row.get("title"),
            "status": row.get(
                "preprocess_status"
            ),
            "current_detected_sections":
                row.get(
                    "detected_sections",
                    [],
                ),
            "heading_candidates":
                unique_candidates[:40],
        }

        results.append(
            result
        )

        print()
        print(
            f"[{index:03d}/{len(targets)}] "
            f"{paper_id} | "
            f"{row.get('preprocess_status')}"
        )

        print(
            "TITLE:",
            row.get("title")
        )

        print(
            "현재 섹션:",
            row.get(
                "detected_sections"
            )
        )

        print("제목 후보:")

        if unique_candidates:

            for heading in unique_candidates[:15]:

                print(
                    "  -",
                    heading
                )

        else:

            print(
                "  - 후보 없음"
            )

    output = {
        "total_preprocessed":
            len(rows),

        "target_count":
            len(targets),

        "papers":
            results,

        "frequent_heading_candidates": [
            {
                "heading": heading,
                "count": count,
            }
            for heading, count
            in heading_counter.most_common(
                100
            )
        ],
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("분석 완료")
    print("=" * 72)

    print(
        f"분석 논문 : {len(results)}"
    )

    print()
    print("저장:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()