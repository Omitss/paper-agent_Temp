from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


# =========================================================
# 경로
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

INPUT_FILE = METADATA_DIR / "kci_oai_all.jsonl"

OUTPUT_JSON = METADATA_DIR / "kci_sme_relevant.json"
OUTPUT_CSV = METADATA_DIR / "kci_sme_relevant.csv"


# =========================================================
# 중소기업 관련 표현
# =========================================================

SME_PATTERNS = [
    re.compile(r"중소\s*기업", re.I),
    re.compile(r"중소\s*제조\s*기업", re.I),
    re.compile(r"중소\s*제조업", re.I),
    re.compile(r"중소\s*벤처", re.I),
    re.compile(r"중소기업청", re.I),
    re.compile(r"중소벤처기업부", re.I),
    re.compile(r"소상공인", re.I),
    re.compile(r"벤처\s*기업", re.I),

    re.compile(
        r"\bsmall\s+and\s+medium"
        r"(?:[-\s]+sized)?"
        r"\s+enterprises?\b",
        re.I,
    ),

    re.compile(r"\bSMEs?\b", re.I),
]


# =========================================================
# 핵심 기술
#
# 이 그룹 중 하나 이상이 반드시 있어야 최종 후보로 인정한다.
# 단순 ICT / 정보화 / 클라우드만 있는 논문은 통과시키지 않는다.
# =========================================================

AI_PATTERNS = [
    re.compile(r"인공\s*지능", re.I),

    re.compile(
        r"(?<![A-Za-z])AI(?![A-Za-z])",
        re.I,
    ),

    re.compile(r"생성형\s*AI", re.I),
    re.compile(r"생성형\s*인공\s*지능", re.I),
    re.compile(r"generative\s+AI", re.I),
    re.compile(r"artificial\s+intelligence", re.I),

    re.compile(r"머신\s*러닝", re.I),
    re.compile(r"machine\s+learning", re.I),

    re.compile(r"딥\s*러닝", re.I),
    re.compile(r"deep\s+learning", re.I),
]


DX_PATTERNS = [
    re.compile(r"디지털\s*전환", re.I),
    re.compile(r"digital\s+transformation", re.I),

    # DX가 일반 영단어 내부에서 잡히지 않도록 제한
    re.compile(
        r"(?<![A-Za-z])DX(?![A-Za-z])",
        re.I,
    ),
]


SMART_FACTORY_PATTERNS = [
    re.compile(r"스마트\s*공장", re.I),
    re.compile(r"스마트\s*팩토리", re.I),
    re.compile(r"스마트\s*제조", re.I),

    re.compile(
        r"\bsmart\s+factor(?:y|ies)\b",
        re.I,
    ),

    re.compile(
        r"\bsmart\s+manufacturing\b",
        re.I,
    ),

    re.compile(r"제조\s*AI", re.I),
]


DATA_INTELLIGENCE_PATTERNS = [
    re.compile(r"빅\s*데이터", re.I),
    re.compile(r"\bbig\s+data\b", re.I),

    re.compile(r"데이터\s*기반", re.I),
    re.compile(r"data[-\s]*driven", re.I),

    re.compile(r"지능화", re.I),
    re.compile(r"지능형", re.I),
]


# =========================================================
# 보조 디지털 기술
#
# 이것만 있다고 논문을 통과시키지는 않는다.
# 핵심 기술 논문의 관련도/점수를 보강하는 용도다.
# =========================================================

SUPPORT_TECH_PATTERNS = [
    re.compile(r"디지털\s*기술", re.I),
    re.compile(r"디지털화", re.I),

    re.compile(r"정보\s*기술", re.I),
    re.compile(r"정보화", re.I),

    re.compile(r"자동화", re.I),

    re.compile(r"클라우드", re.I),
    re.compile(r"\bcloud\b", re.I),

    # ICT도 영단어 내부 오탐 방지
    re.compile(
        r"(?<![A-Za-z])ICT(?![A-Za-z])",
        re.I,
    ),

    re.compile(r"산업\s*4\.?0", re.I),
    re.compile(r"4차\s*산업", re.I),

    re.compile(r"사물\s*인터넷", re.I),
    re.compile(r"\bIoT\b", re.I),
]


# =========================================================
# 경영 / 경제 성과 관련 표현
# =========================================================

PERFORMANCE_PATTERNS = [
    re.compile(r"경영\s*성과", re.I),
    re.compile(r"기업\s*성과", re.I),
    re.compile(r"사업\s*성과", re.I),

    re.compile(r"재무\s*성과", re.I),
    re.compile(r"비재무\s*성과", re.I),

    re.compile(r"생산성", re.I),

    re.compile(r"업무\s*효율", re.I),
    re.compile(r"운영\s*효율", re.I),

    re.compile(r"매출", re.I),
    re.compile(r"매출액", re.I),

    re.compile(r"수익성", re.I),
    re.compile(r"영업\s*이익", re.I),

    re.compile(r"경쟁력", re.I),

    re.compile(r"혁신\s*성과", re.I),
    re.compile(r"혁신\s*역량", re.I),

    re.compile(r"기업\s*성장", re.I),
    re.compile(r"성장\s*성과", re.I),

    re.compile(r"고용\s*성과", re.I),
    re.compile(r"고용\s*증가", re.I),

    re.compile(r"수출\s*성과", re.I),
    re.compile(r"수출\s*경쟁력", re.I),

    re.compile(r"\bperformance\b", re.I),
    re.compile(r"\bproductivity\b", re.I),
    re.compile(r"\bprofitability\b", re.I),
    re.compile(r"\bcompetitiveness\b", re.I),
    re.compile(r"\binnovation\s+performance\b", re.I),
    re.compile(r"\bbusiness\s+performance\b", re.I),
    re.compile(r"\bfirm\s+performance\b", re.I),
]


# =========================================================
# 유틸
# =========================================================

def join_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(
            str(x)
            for x in value
            if x is not None
        )

    return str(value or "")


def matches(
    text: str,
    patterns: list[re.Pattern],
) -> list[str]:

    found: list[str] = []

    for pattern in patterns:
        match = pattern.search(text)

        if not match:
            continue

        value = match.group(0).strip()

        if not value:
            continue

        if value.lower() not in {
            x.lower()
            for x in found
        }:
            found.append(value)

    return found


def merge_matches(
    *groups: list[str],
) -> list[str]:

    result: list[str] = []

    for group in groups:
        for value in group:
            if value.lower() not in {
                x.lower()
                for x in result
            }:
                result.append(value)

    return result


# =========================================================
# 관련성 판단
# =========================================================

def classify(
    paper: dict[str, Any],
) -> dict[str, Any] | None:

    title = str(
        paper.get("title", "")
        or ""
    )

    title_en = str(
        paper.get("title_en", "")
        or ""
    )

    abstract = str(
        paper.get("abstract", "")
        or ""
    )

    abstract_en = str(
        paper.get("abstract_en", "")
        or ""
    )

    keywords = join_value(
        paper.get("keywords", [])
    )

    category = join_value(
        paper.get("category", "")
    )

    # -----------------------------------------------------
    # 제목 + 키워드는 가장 중요한 영역
    # -----------------------------------------------------

    title_keyword_text = " ".join(
        [
            title,
            title_en,
            keywords,
        ]
    )

    all_text = " ".join(
        [
            title_keyword_text,
            abstract,
            abstract_en,
            category,
        ]
    )

    # -----------------------------------------------------
    # 1. SME 조건
    # -----------------------------------------------------

    sme_title_matches = matches(
        title_keyword_text,
        SME_PATTERNS,
    )

    sme_all_matches = matches(
        all_text,
        SME_PATTERNS,
    )

    # 중소기업 관련 내용이 없으면 즉시 제외
    if not sme_all_matches:
        return None

    # -----------------------------------------------------
    # 2. 핵심 기술 조건
    # -----------------------------------------------------

    ai_title_matches = matches(
        title_keyword_text,
        AI_PATTERNS,
    )

    ai_all_matches = matches(
        all_text,
        AI_PATTERNS,
    )

    dx_title_matches = matches(
        title_keyword_text,
        DX_PATTERNS,
    )

    dx_all_matches = matches(
        all_text,
        DX_PATTERNS,
    )

    smart_title_matches = matches(
        title_keyword_text,
        SMART_FACTORY_PATTERNS,
    )

    smart_all_matches = matches(
        all_text,
        SMART_FACTORY_PATTERNS,
    )

    data_title_matches = matches(
        title_keyword_text,
        DATA_INTELLIGENCE_PATTERNS,
    )

    data_all_matches = matches(
        all_text,
        DATA_INTELLIGENCE_PATTERNS,
    )

    core_tech_title_matches = merge_matches(
        ai_title_matches,
        dx_title_matches,
        smart_title_matches,
        data_title_matches,
    )

    core_tech_all_matches = merge_matches(
        ai_all_matches,
        dx_all_matches,
        smart_all_matches,
        data_all_matches,
    )

    # -----------------------------------------------------
    # 핵심 변경점
    #
    # AI / DX / 스마트공장 / 데이터 지능화 중
    # 하나도 없으면 제외한다.
    #
    # 따라서:
    # 중소기업 + ICT
    # 중소기업 + 정보화
    # 중소기업 + 클라우드
    # 만으로는 더 이상 통과하지 않는다.
    # -----------------------------------------------------

    if not core_tech_all_matches:
        return None

    # -----------------------------------------------------
    # 3. 보조 기술
    # -----------------------------------------------------

    support_title_matches = matches(
        title_keyword_text,
        SUPPORT_TECH_PATTERNS,
    )

    support_all_matches = matches(
        all_text,
        SUPPORT_TECH_PATTERNS,
    )

    # -----------------------------------------------------
    # 4. 경제 / 경영 성과
    # -----------------------------------------------------

    performance_title_matches = matches(
        title_keyword_text,
        PERFORMANCE_PATTERNS,
    )

    performance_all_matches = matches(
        all_text,
        PERFORMANCE_PATTERNS,
    )

    # -----------------------------------------------------
    # 5. 관련도 점수
    # -----------------------------------------------------

    score = 0

    # 중소기업이 제목/키워드에 직접 등장하면 강하게 가점
    if sme_title_matches:
        score += 5
    else:
        score += 2

    # AI가 가장 직접적인 주제
    if ai_title_matches:
        score += 8
    elif ai_all_matches:
        score += 5

    # 디지털 전환
    if dx_title_matches:
        score += 7
    elif dx_all_matches:
        score += 4

    # 스마트공장 / 스마트제조
    if smart_title_matches:
        score += 6
    elif smart_all_matches:
        score += 4

    # 빅데이터 / 데이터 기반 / 지능화
    if data_title_matches:
        score += 4
    elif data_all_matches:
        score += 2

    # 보조 기술
    if support_title_matches:
        score += 2
    elif support_all_matches:
        score += 1

    # 경제/경영성과
    if performance_title_matches:
        score += 5
    elif performance_all_matches:
        score += 3

    # -----------------------------------------------------
    # 6. 등급
    #
    # core:
    # SME + 핵심 기술 + 경영성과
    #
    # high:
    # SME + 핵심 기술
    #
    # support는 이제 최종 후보에서 만들지 않는다.
    # -----------------------------------------------------

    if performance_all_matches:
        relevance = "core"
    else:
        relevance = "high"

    # -----------------------------------------------------
    # 기술 세부 유형
    # -----------------------------------------------------

    tech_types: list[str] = []

    if ai_all_matches:
        tech_types.append("AI")

    if dx_all_matches:
        tech_types.append("DX")

    if smart_all_matches:
        tech_types.append("SMART_FACTORY")

    if data_all_matches:
        tech_types.append("DATA_INTELLIGENCE")

    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    result = dict(paper)

    result["relevance"] = relevance
    result["relevance_score"] = score

    result["sme_matches"] = sme_all_matches

    result["tech_types"] = tech_types

    result["ai_matches"] = ai_all_matches
    result["dx_matches"] = dx_all_matches
    result["smart_factory_matches"] = smart_all_matches
    result["data_intelligence_matches"] = data_all_matches

    result["tech_strong_matches"] = core_tech_all_matches
    result["tech_support_matches"] = support_all_matches

    result["performance_matches"] = performance_all_matches

    return result


# =========================================================
# 중복 제거
# =========================================================

def deduplicate(
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for paper in papers:

        article_id = str(
            paper.get("article_id", "")
            or ""
        ).strip()

        identifier = str(
            paper.get("identifier", "")
            or ""
        ).strip()

        doi = str(
            paper.get("doi", "")
            or ""
        ).strip().lower()

        title = re.sub(
            r"\s+",
            "",
            str(
                paper.get("title", "")
                or ""
            ).lower(),
        )

        if article_id:
            key = (
                "article_id",
                article_id,
            )

        elif doi:
            key = (
                "doi",
                doi,
            )

        elif identifier:
            key = (
                "identifier",
                identifier,
            )

        else:
            key = (
                "title",
                title,
            )

        if key in seen:
            continue

        seen.add(key)
        result.append(paper)

    return result


# =========================================================
# 저장
# =========================================================

def save_json(
    papers: list[dict[str, Any]],
) -> None:

    METADATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            papers,
            f,
            ensure_ascii=False,
            indent=2,
        )


def save_csv(
    papers: list[dict[str, Any]],
) -> None:

    columns = [
        "relevance",
        "relevance_score",

        "article_id",
        "identifier",

        "title",
        "title_en",

        "authors",
        "publication_year",

        "publisher",
        "journal",

        "category",
        "keywords",

        "open_access",
        "format",

        "doi",
        "landing_url",

        "tech_types",

        "sme_matches",

        "ai_matches",
        "dx_matches",
        "smart_factory_matches",
        "data_intelligence_matches",

        "tech_strong_matches",
        "tech_support_matches",

        "performance_matches",

        "metadata_type",
        "datestamp",
    ]

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for paper in papers:

            row = dict(paper)

            list_fields = [
                "authors",
                "keywords",
                "tech_types",
                "sme_matches",
                "ai_matches",
                "dx_matches",
                "smart_factory_matches",
                "data_intelligence_matches",
                "tech_strong_matches",
                "tech_support_matches",
                "performance_matches",
            ]

            for field in list_fields:

                value = row.get(
                    field,
                    [],
                )

                if isinstance(
                    value,
                    list,
                ):
                    row[field] = " | ".join(
                        str(x)
                        for x in value
                    )

            writer.writerow(row)


# =========================================================
# main
# =========================================================

def main():

    print()
    print("=" * 90)
    print(
        "KCI 중소기업 + AI/DX "
        "정밀 논문 필터링"
    )
    print("=" * 90)

    if not INPUT_FILE.exists():

        print(
            "[ERROR] 원본 메타데이터 없음:"
        )
        print(INPUT_FILE)

        return

    scanned = 0
    parse_errors = 0

    matched: list[dict[str, Any]] = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            scanned += 1

            try:
                paper = json.loads(line)

            except Exception:
                parse_errors += 1
                continue

            result = classify(paper)

            if result is not None:
                matched.append(result)

    # -----------------------------------------------------
    # 중복 제거
    # -----------------------------------------------------

    matched = deduplicate(matched)

    # -----------------------------------------------------
    # 관련도 정렬
    #
    # core 우선
    # → 점수
    # → 최신 연도
    # -----------------------------------------------------

    relevance_order = {
        "core": 2,
        "high": 1,
    }

    def sort_key(
        paper: dict[str, Any],
    ) -> tuple:

        relevance = relevance_order.get(
            str(
                paper.get(
                    "relevance",
                    "",
                )
            ),
            0,
        )

        score = int(
            paper.get(
                "relevance_score",
                0,
            )
            or 0
        )

        year_text = str(
            paper.get(
                "publication_year",
                "",
            )
            or ""
        )

        year_match = re.search(
            r"\d{4}",
            year_text,
        )

        year = (
            int(year_match.group(0))
            if year_match
            else 0
        )

        return (
            relevance,
            score,
            year,
        )

    matched.sort(
        key=sort_key,
        reverse=True,
    )

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    save_json(matched)
    save_csv(matched)

    # -----------------------------------------------------
    # 통계
    # -----------------------------------------------------

    core = sum(
        1
        for x in matched
        if x.get("relevance") == "core"
    )

    high = sum(
        1
        for x in matched
        if x.get("relevance") == "high"
    )

    open_access = sum(
        1
        for x in matched
        if str(
            x.get(
                "open_access",
                "",
            )
        ).upper() == "Y"
    )

    pdf_format = sum(
        1
        for x in matched
        if "pdf"
        in str(
            x.get(
                "format",
                "",
            )
        ).lower()
    )

    ai_count = sum(
        1
        for x in matched
        if x.get("ai_matches")
    )

    dx_count = sum(
        1
        for x in matched
        if x.get("dx_matches")
    )

    smart_count = sum(
        1
        for x in matched
        if x.get(
            "smart_factory_matches"
        )
    )

    data_count = sum(
        1
        for x in matched
        if x.get(
            "data_intelligence_matches"
        )
    )

    # -----------------------------------------------------
    # 출력
    # -----------------------------------------------------

    print()
    print("[FILTER RESULT]")

    print(
        "전체 검사       :",
        f"{scanned:,}",
    )

    print(
        "파싱 오류       :",
        f"{parse_errors:,}",
    )

    print(
        "정밀 관련 논문  :",
        f"{len(matched):,}",
    )

    print(
        "core            :",
        f"{core:,}",
    )

    print(
        "high            :",
        f"{high:,}",
    )

    print(
        "원문공개 Y      :",
        f"{open_access:,}",
    )

    print(
        "format=pdf      :",
        f"{pdf_format:,}",
    )

    print()
    print("[TECH TYPE]")

    print(
        "AI 포함         :",
        f"{ai_count:,}",
    )

    print(
        "DX 포함         :",
        f"{dx_count:,}",
    )

    print(
        "스마트공장 포함 :",
        f"{smart_count:,}",
    )

    print(
        "데이터/지능화   :",
        f"{data_count:,}",
    )

    # -----------------------------------------------------
    # TOP 50
    # -----------------------------------------------------

    print()
    print("[TOP 50]")

    for index, paper in enumerate(
        matched[:50],
        start=1,
    ):

        print()

        print(
            f"{index:02d}. "
            f"[{paper['relevance']}] "
            f"score={paper['relevance_score']}"
        )

        print(
            "     ",
            paper.get(
                "title",
                "",
            ),
        )

        print(
            "     year:",
            paper.get(
                "publication_year",
                "",
            ),
            "| OA:",
            paper.get(
                "open_access",
                "",
            ),
            "| format:",
            paper.get(
                "format",
                "",
            ),
        )

        print(
            "     TYPE:",
            paper.get(
                "tech_types",
                [],
            ),
        )

        print(
            "     SME :",
            paper.get(
                "sme_matches",
                [],
            ),
        )

        print(
            "     TECH:",
            paper.get(
                "tech_strong_matches",
                [],
            ),
        )

        print(
            "     PERF:",
            paper.get(
                "performance_matches",
                [],
            ),
        )

    print()
    print("[SAVED]")
    print(OUTPUT_JSON)
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()