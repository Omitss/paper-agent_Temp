import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_deduplicated.jsonl"
)

TEXT_DIR = PROJECT_ROOT / "data" / "text"

CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"

OUTPUT_METADATA = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

REVIEW_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocess_review.jsonl"
)

CLEANED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 섹션 패턴
# ============================================================

SECTION_PATTERNS = [
    (
        "abstract",
        re.compile(
            r"^\s*(?:국문\s*)?초록\s*$"
            r"|^\s*abstract\s*$",
            re.I,
        ),
    ),

    (
        "introduction",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅠI1]\.?\s*)?"
            r"(?:서\s*론|연구의\s*배경|연구\s*배경)"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "literature_review",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅡII2]\.?\s*)?"
            r"(?:"
            r"이론적\s*배경|"
            r"이론적\s*고찰|"
            r"선행연구|"
            r"문헌연구|"
            r"문헌\s*고찰|"
            r"관련\s*연구"
            r")"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "methodology",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅢIII3]\.?\s*)?"
            r"(?:"
            r"연구방법|"
            r"연구\s*방법|"
            r"연구설계|"
            r"연구\s*설계|"
            r"연구모형|"
            r"연구\s*모형|"
            r"분석방법|"
            r"분석\s*방법"
            r")"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "results",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅣIV4]\.?\s*)?"
            r"(?:"
            r"연구결과|"
            r"연구\s*결과|"
            r"분석결과|"
            r"분석\s*결과|"
            r"실증분석|"
            r"실증\s*분석"
            r")"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "discussion",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅤV5]\.?\s*)?"
            r"(?:논의|고찰)"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "conclusion",
        re.compile(
            r"^\s*(?:"
            r"(?:[ⅤⅥVVI56]\.?\s*)?"
            r"(?:"
            r"결론|"
            r"결\s*론|"
            r"결론\s*및\s*제언|"
            r"결론\s*및\s*시사점|"
            r"요약\s*및\s*결론|"
            r"결론\s*및\s*향후\s*연구"
            r")"
            r")\s*$",
            re.I,
        ),
    ),

    (
        "references",
        re.compile(
            r"^\s*(?:"
            r"참고문헌|"
            r"참고\s*문헌|"
            r"references|"
            r"bibliography"
            r")\s*$",
            re.I,
        ),
    ),
]


# ============================================================
# JSONL
# ============================================================

def load_jsonl(path):

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            rows.append(
                json.loads(line)
            )

    return rows


def write_jsonl(path, rows):

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        for row in rows:

            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


# ============================================================
# 기본 정규화
# ============================================================

def normalize_text(text):

    # Unicode 정규화
    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    # BOM / null 제거
    text = text.replace(
        "\ufeff",
        "",
    )

    text = text.replace(
        "\x00",
        "",
    )

    # PDF 추출 페이지 구분자 제거
    text = re.sub(
        r"(?m)^===== PAGE \d+ =====\s*$",
        "",
        text,
    )

    # 줄 끝 공백 제거
    lines = [
        line.rstrip()
        for line in text.splitlines()
    ]

    # 공백만 있는 줄 정리
    cleaned_lines = []

    blank = False

    for line in lines:

        if not line.strip():

            if not blank:
                cleaned_lines.append("")

            blank = True

        else:
            cleaned_lines.append(line)
            blank = False

    text = "\n".join(
        cleaned_lines
    )

    # 3줄 이상 빈 줄 → 2줄
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# 반복 Header / Footer 후보 제거
# ============================================================

def remove_repeated_short_lines(text):

    lines = text.splitlines()

    normalized = [
        re.sub(
            r"\s+",
            " ",
            line.strip(),
        )
        for line in lines
    ]

    counts = Counter(
        line
        for line in normalized
        if (
            line
            and len(line) <= 80
        )
    )

    # 여러 페이지에서 반복되는 짧은 문구
    repeated = {
        line
        for line, count in counts.items()
        if count >= 4
    }

    output = []

    removed = 0

    for original, norm in zip(
        lines,
        normalized,
    ):

        # 숫자만 있는 페이지 번호
        if re.fullmatch(
            r"\s*-?\s*\d{1,4}\s*-?\s*",
            original,
        ):
            removed += 1
            continue

        # 반복되는 짧은 header/footer
        if norm in repeated:
            removed += 1
            continue

        output.append(original)

    return (
        "\n".join(output),
        removed,
        sorted(repeated),
    )


# ============================================================
# 문장 내부 공백/줄바꿈 보정
# ============================================================

def repair_line_breaks(text):

    lines = text.splitlines()

    output = []

    buffer = ""

    def flush():

        nonlocal buffer

        if buffer.strip():
            output.append(
                buffer.strip()
            )

        buffer = ""

    for line in lines:

        stripped = line.strip()

        if not stripped:

            flush()

            if (
                output
                and output[-1] != ""
            ):
                output.append("")

            continue

        # 섹션 제목 후보는 줄을 합치지 않음
        if detect_section(stripped):

            flush()
            output.append(stripped)
            continue

        # 표/수식 가능성이 높은 짧은 줄은 보존
        if (
            len(stripped) <= 2
            or "\t" in line
        ):
            flush()
            output.append(stripped)
            continue

        if not buffer:

            buffer = stripped
            continue

        previous = buffer.rstrip()

        # 이전 줄이 문장 종결이면 새 문장
        if re.search(
            r"[.!?。！？]\s*$",
            previous,
        ):

            flush()
            buffer = stripped

        else:

            # 한글/영문 문장 줄바꿈을 공백으로 연결
            buffer += " " + stripped

    flush()

    text = "\n".join(output)

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# 섹션 탐지
# ============================================================

def detect_section(line):

    value = re.sub(
        r"\s+",
        " ",
        line.strip(),
    )

    # 너무 긴 문장은 제목으로 보지 않음
    if len(value) > 80:
        return None

    for section_name, pattern in SECTION_PATTERNS:

        if pattern.match(value):
            return section_name

    return None


def split_sections(text):

    lines = text.splitlines()

    sections = []

    current_section = "front_matter"
    current_title = None
    buffer = []

    for line in lines:

        detected = detect_section(
            line
        )

        if detected:

            content = "\n".join(
                buffer
            ).strip()

            if content:

                sections.append(
                    {
                        "section": current_section,
                        "title": current_title,
                        "content": content,
                    }
                )

            current_section = detected
            current_title = line.strip()
            buffer = []

        else:

            buffer.append(line)

    content = "\n".join(
        buffer
    ).strip()

    if content:

        sections.append(
            {
                "section": current_section,
                "title": current_title,
                "content": content,
            }
        )

    return sections


# ============================================================
# 품질 판정
# ============================================================

def evaluate_quality(
    raw_chars,
    cleaned_chars,
    sections,
):

    detected_sections = {
        section["section"]
        for section in sections
        if section["section"] != "front_matter"
    }

    section_count = len(
        detected_sections
    )

    reasons = []

    if cleaned_chars < 1000:

        status = "LOW_TEXT"

        reasons.append(
            "cleaned_text_under_1000_chars"
        )

    elif cleaned_chars < 3000:

        status = "VERY_SHORT"

        reasons.append(
            "cleaned_text_under_3000_chars"
        )

    elif section_count == 0:

        status = "SECTION_FAILED"

        reasons.append(
            "no_major_section_detected"
        )

    elif section_count < 2:

        status = "LOW_SECTION_DETECTION"

        reasons.append(
            "fewer_than_2_sections_detected"
        )

    else:

        status = "OK"

    if (
        raw_chars > 0
        and cleaned_chars / raw_chars < 0.35
    ):

        reasons.append(
            "large_text_reduction"
        )

        if status == "OK":
            status = "REVIEW"

    return (
        status,
        reasons,
        sorted(detected_sections),
    )


# ============================================================
# 개별 논문 처리
# ============================================================

def preprocess_paper(row):

    paper_id = row["paper_id"]

    text_path_value = row.get(
        "text_file"
    )

    if text_path_value:

        text_path = Path(
            text_path_value
        )

    else:

        text_path = (
            TEXT_DIR
            / f"{paper_id}.txt"
        )

    if not text_path.exists():

        return None, {
            "paper_id": paper_id,
            "status": "TEXT_FILE_NOT_FOUND",
            "text_path": str(text_path),
        }

    raw_text = text_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    raw_chars = len(
        raw_text
    )

    text = normalize_text(
        raw_text
    )

    (
        text,
        removed_repeated_lines,
        repeated_lines,
    ) = remove_repeated_short_lines(
        text
    )

    text = repair_line_breaks(
        text
    )

    sections = split_sections(
        text
    )

    cleaned_chars = len(
        text
    )

    (
        quality_status,
        quality_reasons,
        detected_sections,
    ) = evaluate_quality(
        raw_chars,
        cleaned_chars,
        sections,
    )

    output_path = (
        CLEANED_DIR
        / f"{paper_id}.json"
    )

    output_data = {
        "paper_id": paper_id,

        "title": row.get("title"),

        "metadata": {
            "authors": row.get("authors"),
            "year": row.get("year"),
            "doi": row.get("doi"),
            "journal": row.get("journal"),
            "document_type": row.get(
                "document_type"
            ),
        },

        "quality": {
            "status": quality_status,
            "reasons": quality_reasons,
            "raw_chars": raw_chars,
            "cleaned_chars": cleaned_chars,
            "section_count": len(
                detected_sections
            ),
            "detected_sections":
                detected_sections,
            "removed_repeated_lines":
                removed_repeated_lines,
        },

        # 디버깅용. 너무 많은 내용은 저장하지 않음.
        "preprocessing": {
            "repeated_line_candidates":
                repeated_lines[:30],
        },

        "full_text": text,

        "sections": sections,
    }

    output_path.write_text(
        json.dumps(
            output_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metadata_row = dict(row)

    metadata_row.update(
        {
            "cleaned_file":
                str(output_path),

            "preprocess_status":
                quality_status,

            "raw_chars":
                raw_chars,

            "cleaned_chars":
                cleaned_chars,

            "detected_sections":
                detected_sections,

            "section_count":
                len(detected_sections),

            "removed_repeated_lines":
                removed_repeated_lines,
        }
    )

    return (
        metadata_row,
        output_data,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    papers = load_jsonl(
        METADATA_FILE
    )

    processed = []
    review = []

    status_counter = Counter()

    print("=" * 72)
    print("05_preprocess")
    print("=" * 72)

    print(
        f"입력 논문 : {len(papers)}"
    )

    print()

    for index, row in enumerate(
        papers,
        start=1,
    ):

        paper_id = row["paper_id"]

        result, detail = preprocess_paper(
            row
        )

        if result is None:

            status = detail["status"]

            status_counter[status] += 1

            review.append(detail)

            print(
                f"[{index:03d}/{len(papers)}] "
                f"{paper_id} | {status}"
            )

            continue

        processed.append(
            result
        )

        status = result[
            "preprocess_status"
        ]

        status_counter[status] += 1

        if status != "OK":

            review.append(
                {
                    "paper_id":
                        paper_id,

                    "title":
                        result.get("title"),

                    "status":
                        status,

                    "raw_chars":
                        result.get("raw_chars"),

                    "cleaned_chars":
                        result.get(
                            "cleaned_chars"
                        ),

                    "section_count":
                        result.get(
                            "section_count"
                        ),

                    "detected_sections":
                        result.get(
                            "detected_sections"
                        ),
                }
            )

        print(
            f"[{index:03d}/{len(papers)}] "
            f"{paper_id} | "
            f"{status} | "
            f"{result['cleaned_chars']:,} chars | "
            f"{result['section_count']} sections"
        )

    write_jsonl(
        OUTPUT_METADATA,
        processed,
    )

    write_jsonl(
        REVIEW_FILE,
        review,
    )

    print()
    print("=" * 72)
    print("전처리 완료")
    print("=" * 72)

    print(
        f"입력 논문           : {len(papers)}"
    )

    print(
        f"처리 성공           : {len(processed)}"
    )

    print(
        f"검토 대상           : {len(review)}"
    )

    print()
    print("[상태]")

    for status, count in sorted(
        status_counter.items()
    ):

        print(
            f"{status:<24}: {count}"
        )

    print()
    print("전처리 메타데이터:")
    print(OUTPUT_METADATA)

    print()
    print("검토 대상:")
    print(REVIEW_FILE)

    print()
    print("정제 파일:")
    print(CLEANED_DIR)


if __name__ == "__main__":
    main()