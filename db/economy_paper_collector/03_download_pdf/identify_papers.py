from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PDF_DIR = PROJECT_ROOT / "data" / "pdf"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

INSPECTION_FILE = METADATA_DIR / "pdf_inspection.json"

OUTPUT_FILE = (
    METADATA_DIR
    / "paper_identity_candidates_v2.json"
)


# ============================================================
# 기본 정리
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", " ")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def compact_spaces(text: str) -> str:
    """
    PDF에서
    최
    석
    원

    같이 떨어진 글자를 그대로 합치지는 않는다.
    일반적인 공백만 정리한다.
    """

    return re.sub(
        r"[ \t]+",
        " ",
        text,
    ).strip()


# ============================================================
# 라이선스 / 안내 페이지 판별
# ============================================================

LICENSE_KEYWORDS = [
    "저작자표시-비영리-변경금지",
    "이용허락규약",
    "저작권법에 따른 이용자의 권리",
    "귀하는 원저작자를 표시하여야 합니다",
    "영리 목적으로 이용할 수 없습니다",
    "변경금지",
]


def is_license_page(text: str) -> bool:
    text = clean_text(text)

    score = 0

    for keyword in LICENSE_KEYWORDS:
        if keyword in text:
            score += 1

    return score >= 2


# ============================================================
# 목차 판별
# ============================================================

def is_toc_page(text: str) -> bool:
    text = clean_text(text)

    if re.search(
        r"목\s*차",
        text,
    ):
        return True

    if (
        "CONTENTS" in text.upper()
        and len(text) < 10000
    ):
        return True

    return False


# ============================================================
# 초록 판별
# ============================================================

def detect_abstract_type(text: str):
    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    if "국문요약" in compact:
        return "KOREAN_ABSTRACT"

    if "국문초록" in compact:
        return "KOREAN_ABSTRACT"

    if re.search(
        r"\bABSTRACT\b",
        text,
        re.IGNORECASE,
    ):
        return "ENGLISH_ABSTRACT"

    return None


# ============================================================
# 학위논문 판별
# ============================================================

THESIS_PATTERNS = [
    r"박사\s*학위\s*논문",
    r"석사\s*학위\s*논문",
    r"박사학위논문",
    r"석사학위논문",
    r"학위논문으로\s*제출",
    r"대학원",
    r"지도교수",
]


def thesis_score(text: str) -> int:
    score = 0

    for pattern in THESIS_PATTERNS:
        if re.search(pattern, text):
            score += 1

    return score


def detect_document_type(
    page_texts: list[str],
):
    combined = "\n".join(
        page_texts[:10]
    )

    score = thesis_score(combined)

    if score >= 2:
        return "THESIS"

    return "JOURNAL_OR_OTHER"


# ============================================================
# DOI
# ============================================================

DOI_PATTERN = re.compile(
    r"""
    (?:
        https?://(?:dx\.)?doi\.org/
    )?
    (
        10\.\d{4,9}/
        [-._;()/:A-Z0-9]+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def find_doi(text: str):
    matches = DOI_PATTERN.findall(text)

    if not matches:
        return None

    doi = matches[0].strip()

    return doi.rstrip(
        ".,;:)]}>"
    )


# ============================================================
# 연도 후보
# ============================================================

YEAR_PATTERN = re.compile(
    r"\b(19[8-9]\d|20[0-3]\d)\b"
)


def find_year_candidates(text: str):
    values = YEAR_PATTERN.findall(text)

    years = [
        int(value)
        for value in values
    ]

    counts = Counter(years)

    return [
        {
            "year": year,
            "count": count,
        }
        for year, count
        in counts.most_common()
    ]


# ============================================================
# KCI ID
# ============================================================

KCI_PATTERN = re.compile(
    r"\bART\d{6,}\b",
    re.IGNORECASE,
)


def find_kci_ids(text: str):
    values = KCI_PATTERN.findall(text)

    return sorted(
        set(
            value.upper()
            for value in values
        )
    )


# ============================================================
# 학위 종류
# ============================================================

def detect_degree(text: str):
    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    if "박사학위논문" in compact:
        return "DOCTORAL"

    if "석사학위논문" in compact:
        return "MASTER"

    return None


# ============================================================
# 제목 후보용 제외 문구
# ============================================================

BAD_LINES = [
    "저작자표시",
    "비영리",
    "변경금지",
    "이용자는",
    "이용허락",
    "저작권",
    "Disclaimer",
    "대학원",
    "지도교수",
    "학위논문",
    "논문으로 제출",
    "국문요약",
    "국문초록",
    "Abstract",
    "목 차",
    "목차",
]


def bad_title_line(line: str):
    line = line.strip()

    if not line:
        return True

    if len(line) < 4:
        return True

    if len(line) > 180:
        return True

    for keyword in BAD_LINES:
        if keyword.lower() in line.lower():
            return True

    # 날짜
    if re.fullmatch(
        r"\d{4}\s*년.*",
        line,
    ):
        return True

    # 숫자/기호 위주
    letters = re.findall(
        r"[가-힣A-Za-z]",
        line,
    )

    if len(letters) < 3:
        return True

    return False


# ============================================================
# 페이지별 제목 후보
# ============================================================

def title_candidates_from_page(
    text: str,
):
    lines = [
        compact_spaces(line)
        for line
        in text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    candidates = []

    # 한 줄
    for line in lines[:40]:

        if bad_title_line(line):
            continue

        candidates.append(line)

    # 두 줄 결합
    for i in range(
        min(len(lines) - 1, 30)
    ):
        a = lines[i]
        b = lines[i + 1]

        if (
            bad_title_line(a)
            or bad_title_line(b)
        ):
            continue

        combined = f"{a} {b}"

        if len(combined) <= 220:
            candidates.append(combined)

    # 세 줄 결합
    for i in range(
        min(len(lines) - 2, 20)
    ):
        a = lines[i]
        b = lines[i + 1]
        c = lines[i + 2]

        if (
            bad_title_line(a)
            or bad_title_line(b)
            or bad_title_line(c)
        ):
            continue

        combined = f"{a} {b} {c}"

        if len(combined) <= 250:
            candidates.append(combined)

    unique = []
    seen = set()

    for candidate in candidates:

        normalized = re.sub(
            r"\s+",
            "",
            candidate,
        ).lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(candidate)

    return unique[:20]


# ============================================================
# 제목 후보 점수
# ============================================================

def score_title_candidate(
    title: str,
    document_type: str,
):
    score = 0

    length = len(title)

    # 적당한 제목 길이
    if 15 <= length <= 120:
        score += 4

    elif 8 <= length <= 180:
        score += 2

    # 연구 제목에 흔한 표현
    title_keywords = [
        "영향",
        "분석",
        "연구",
        "효과",
        "관계",
        "중소기업",
        "인공지능",
        "AI",
        "디지털",
        "성과",
        "효율성",
        "정책",
        "도입",
        "활용",
    ]

    for keyword in title_keywords:
        if keyword.lower() in title.lower():
            score += 1

    # 제목에 콜론이 있으면 가산
    if ":" in title:
        score += 1

    # 영어 비중이 지나치게 높으면
    # 한국어 논문 제목 후보에서는 약간 감점
    korean = len(
        re.findall(r"[가-힣]", title)
    )

    english = len(
        re.findall(r"[A-Za-z]", title)
    )

    if korean >= 5:
        score += 2

    if english > korean * 3:
        score -= 1

    # 명백한 기관/학위 정보
    bad_keywords = [
        "대학교",
        "대학원",
        "지도교수",
        "학위논문",
        "제출함",
        "저작자표시",
        "국문요약",
        "목차",
    ]

    for keyword in bad_keywords:
        if keyword in title:
            score -= 10

    return score


# ============================================================
# PDF 읽기
# ============================================================

def read_pages(
    pdf_path: Path,
    max_pages: int = 15,
):
    document = pymupdf.open(pdf_path)

    try:
        page_count = document.page_count

        metadata = document.metadata or {}

        page_texts = []

        limit = min(
            max_pages,
            page_count,
        )

        for index in range(limit):

            try:
                page = document.load_page(
                    index
                )

                text = page.get_text(
                    "text"
                ) or ""

                page_texts.append(
                    clean_text(text)
                )

            except Exception:
                page_texts.append("")

        return (
            page_count,
            metadata,
            page_texts,
        )

    finally:
        document.close()


# ============================================================
# 중복 Map
# ============================================================

def build_duplicate_map(
    inspection: dict,
):
    result = {}

    groups = inspection.get(
        "duplicate_groups",
        {},
    )

    for filenames in groups.values():

        filenames = sorted(filenames)

        if not filenames:
            continue

        representative = filenames[0]

        for filename in filenames:

            result[filename] = {
                "representative": representative,
                "is_representative": (
                    filename == representative
                ),
            }

    return result


# ============================================================
# 논문 식별
# ============================================================

def identify(
    record: dict,
    duplicate_info,
):
    filename = record["filename"]

    pdf_path = PDF_DIR / filename

    result = {
        "source_filename": filename,
        "sha256": record.get("sha256"),

        "inspection_status": (
            record.get("status")
        ),

        "processing_status": "PENDING",

        "binary_duplicate": False,
        "duplicate_representative": None,

        "document_type": None,
        "degree": None,

        "page_count": (
            record.get("page_count", 0)
        ),

        "license_pages": [],
        "abstract_pages": [],
        "toc_pages": [],

        "likely_start_page": None,

        "title": None,
        "title_score": None,
        "title_page": None,

        "title_candidates": [],

        "doi": None,
        "kci_ids": [],

        "year_candidates": [],

        "pdf_metadata_title": None,
        "pdf_metadata_author": None,

        "error": None,
    }

    # --------------------------------------------------------
    # 완전 중복
    # --------------------------------------------------------

    if duplicate_info:

        result[
            "duplicate_representative"
        ] = duplicate_info[
            "representative"
        ]

        if not duplicate_info[
            "is_representative"
        ]:

            result[
                "binary_duplicate"
            ] = True

            result[
                "processing_status"
            ] = "SKIP_BINARY_DUPLICATE"

            return result

    # --------------------------------------------------------
    # 텍스트 없음
    # --------------------------------------------------------

    if record.get("status") == "NO_TEXT":

        result[
            "processing_status"
        ] = "NEEDS_OCR_OR_REVIEW"

        return result

    # --------------------------------------------------------
    # PDF 읽기
    # --------------------------------------------------------

    try:
        (
            page_count,
            metadata,
            page_texts,
        ) = read_pages(pdf_path)

        result["page_count"] = page_count

        result[
            "pdf_metadata_title"
        ] = (
            metadata.get("title")
            or None
        )

        result[
            "pdf_metadata_author"
        ] = (
            metadata.get("author")
            or None
        )

        # ----------------------------------------------------
        # 페이지 구조
        # ----------------------------------------------------

        useful_pages = []

        for index, text in enumerate(
            page_texts
        ):
            page_number = index + 1

            if not text:
                continue

            if is_license_page(text):

                result[
                    "license_pages"
                ].append(page_number)

                continue

            abstract_type = (
                detect_abstract_type(text)
            )

            if abstract_type:

                result[
                    "abstract_pages"
                ].append(
                    {
                        "page": page_number,
                        "type": abstract_type,
                    }
                )

            if is_toc_page(text):

                result[
                    "toc_pages"
                ].append(page_number)

            useful_pages.append(
                (
                    page_number,
                    text,
                )
            )

        if useful_pages:
            result[
                "likely_start_page"
            ] = useful_pages[0][0]

        # ----------------------------------------------------
        # 문서 종류
        # ----------------------------------------------------

        result[
            "document_type"
        ] = detect_document_type(
            page_texts
        )

        combined = "\n".join(
            page_texts
        )

        result[
            "degree"
        ] = detect_degree(
            combined
        )

        result["doi"] = find_doi(
            combined
        )

        result[
            "kci_ids"
        ] = find_kci_ids(
            combined
        )

        result[
            "year_candidates"
        ] = find_year_candidates(
            combined
        )

        # ----------------------------------------------------
        # 제목 후보
        # ----------------------------------------------------

        scored_candidates = []

        # 앞쪽 실제 페이지 1~6개만
        # 제목 후보 대상으로 사용
        for (
            page_number,
            text,
        ) in useful_pages[:6]:

            # 초록/목차 페이지는 제목 후보에서 제외
            if is_toc_page(text):
                continue

            if detect_abstract_type(text):
                continue

            candidates = (
                title_candidates_from_page(
                    text
                )
            )

            for candidate in candidates:

                score = (
                    score_title_candidate(
                        candidate,
                        result[
                            "document_type"
                        ],
                    )
                )

                scored_candidates.append(
                    {
                        "title": candidate,
                        "score": score,
                        "page": page_number,
                    }
                )

        # ----------------------------------------------------
        # 중복 후보 제거
        # ----------------------------------------------------

        unique = {}

        for item in scored_candidates:

            normalized = re.sub(
                r"\s+",
                "",
                item["title"],
            ).lower()

            existing = unique.get(
                normalized
            )

            if (
                existing is None
                or item["score"]
                > existing["score"]
            ):
                unique[
                    normalized
                ] = item

        scored_candidates = list(
            unique.values()
        )

        scored_candidates.sort(
            key=lambda x: (
                x["score"],
                -x["page"],
                len(x["title"]),
            ),
            reverse=True,
        )

        result[
            "title_candidates"
        ] = scored_candidates[:10]

        if scored_candidates:

            best = scored_candidates[0]

            result["title"] = best[
                "title"
            ]

            result["title_score"] = best[
                "score"
            ]

            result["title_page"] = best[
                "page"
            ]

        # ----------------------------------------------------
        # 상태
        # ----------------------------------------------------

        if result["title"]:

            result[
                "processing_status"
            ] = "AUTO_IDENTIFIED"

        else:

            result[
                "processing_status"
            ] = "NEEDS_REVIEW"

        return result

    except Exception as e:

        result[
            "processing_status"
        ] = "ERROR"

        result["error"] = str(e)

        return result


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 80)
    print("논문 구조 기반 식별 V2")
    print("=" * 80)

    with INSPECTION_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        inspection = json.load(f)

    duplicate_map = (
        build_duplicate_map(
            inspection
        )
    )

    records = inspection.get(
        "papers",
        [],
    )

    results = []

    for index, record in enumerate(
        records,
        start=1,
    ):
        filename = record["filename"]

        print()
        print(
            f"[{index:03d}/{len(records):03d}] "
            f"{filename}"
        )

        result = identify(
            record,
            duplicate_map.get(filename),
        )

        results.append(result)

        print(
            "    STATUS : "
            f"{result['processing_status']}"
        )

        if result.get(
            "document_type"
        ):
            print(
                "    TYPE   : "
                f"{result['document_type']}"
            )

        if result.get("degree"):
            print(
                "    DEGREE : "
                f"{result['degree']}"
            )

        if result.get("title"):
            print(
                "    TITLE? : "
                f"{result['title']}"
            )

            print(
                "    PAGE   : "
                f"{result['title_page']}"
            )

            print(
                "    SCORE  : "
                f"{result['title_score']}"
            )

    # ========================================================
    # 통계
    # ========================================================

    status_counter = Counter(
        item["processing_status"]
        for item in results
    )

    type_counter = Counter(
        item["document_type"]
        for item in results
        if item["document_type"]
    )

    output = {
        "summary": {
            "total": len(results),
            "status": dict(
                status_counter
            ),
            "document_types": dict(
                type_counter
            ),
        },
        "papers": results,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 80)
    print("V2 식별 완료")
    print("=" * 80)

    print()
    print("[상태]")

    for key, value in sorted(
        status_counter.items()
    ):
        print(
            f"{key:25s}: {value}"
        )

    print()
    print("[문서 종류]")

    for key, value in sorted(
        type_counter.items()
    ):
        print(
            f"{key:25s}: {value}"
        )

    print()
    print("결과:")
    print(OUTPUT_FILE)

    print()
    print(
        "※ 원본 PDF는 수정/삭제하지 않았습니다."
    )


if __name__ == "__main__":
    main()