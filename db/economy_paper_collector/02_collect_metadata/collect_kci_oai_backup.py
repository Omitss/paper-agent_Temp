from __future__ import annotations

import csv
import json
import re
import threading
import time
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import requests


# =========================================================
# 경로
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "metadata"

METADATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

JSON_FILE = (
    METADATA_DIR
    / "kci_relevant_papers.json"
)

CSV_FILE = (
    METADATA_DIR
    / "kci_relevant_papers.csv"
)


# =========================================================
# KCI OAI
# =========================================================

BASE_URL = (
    "https://open.kci.go.kr/oai/request"
)


# =========================================================
# 수집 설정
# =========================================================

MAX_WORKERS = 4

TARGET_RELEVANT = 300

REQUEST_SLEEP = 0.05


# =========================================================
# 중요
#
# 이 날짜는 논문 발행연도가 아니라
# OAI 저장소 datestamp 기준임.
# =========================================================

TODAY = date.today().isoformat()

DATE_RANGES = [
    ("2013-03-21", "2016-12-31"),
    ("2017-01-01", "2020-12-31"),
    ("2021-01-01", "2023-12-31"),
    ("2024-01-01", TODAY),
]


# =========================================================
# 중소기업 관련
# =========================================================

SME_TERMS = [
    "중소기업",
    "중소 기업",
    "중소벤처기업",
    "중소벤처",
    "중소 제조기업",
    "중소 제조업",
    "중소 제조",
    "중소사업자",
    "중소 사업자",
    "소상공인",
    "벤처기업",
    "벤처 기업",
    "스타트업",
    "small and medium enterprise",
    "small and medium enterprises",
    "small and medium-sized enterprise",
    "small and medium-sized enterprises",
    "sme",
    "smes",
]


# =========================================================
# AI / DX 관련
# =========================================================

TECH_PATTERNS = [
    (
        "AI",
        re.compile(
            r"(?<![A-Za-z])AI(?![A-Za-z])",
            re.IGNORECASE,
        ),
    ),
    (
        "인공지능",
        re.compile(
            r"인공지능",
            re.IGNORECASE,
        ),
    ),
    (
        "생성형AI",
        re.compile(
            r"생성형\s*AI",
            re.IGNORECASE,
        ),
    ),
    (
        "Artificial Intelligence",
        re.compile(
            r"\bartificial\s+intelligence\b",
            re.IGNORECASE,
        ),
    ),
    (
        "AI전환",
        re.compile(
            r"AI\s*전환",
            re.IGNORECASE,
        ),
    ),
    (
        "AX",
        re.compile(
            r"(?<![A-Za-z])AX(?![A-Za-z])",
            re.IGNORECASE,
        ),
    ),
    (
        "디지털전환",
        re.compile(
            r"디지털\s*전환",
            re.IGNORECASE,
        ),
    ),
    (
        "Digital Transformation",
        re.compile(
            r"\bdigital\s+transformation\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DX",
        re.compile(
            r"(?<![A-Za-z])DX(?![A-Za-z])",
            re.IGNORECASE,
        ),
    ),
    (
        "스마트공장",
        re.compile(
            r"스마트\s*공장",
            re.IGNORECASE,
        ),
    ),
    (
        "스마트팩토리",
        re.compile(
            r"스마트\s*팩토리",
            re.IGNORECASE,
        ),
    ),
    (
        "Smart Factory",
        re.compile(
            r"\bsmart\s+factor(?:y|ies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "스마트제조",
        re.compile(
            r"스마트\s*제조",
            re.IGNORECASE,
        ),
    ),
    (
        "Smart Manufacturing",
        re.compile(
            r"\bsmart\s+manufacturing\b",
            re.IGNORECASE,
        ),
    ),
    (
        "제조AI",
        re.compile(
            r"제조\s*AI",
            re.IGNORECASE,
        ),
    ),
    (
        "머신러닝",
        re.compile(
            r"머신\s*러닝",
            re.IGNORECASE,
        ),
    ),
    (
        "Machine Learning",
        re.compile(
            r"\bmachine\s+learning\b",
            re.IGNORECASE,
        ),
    ),
    (
        "딥러닝",
        re.compile(
            r"딥\s*러닝",
            re.IGNORECASE,
        ),
    ),
    (
        "Deep Learning",
        re.compile(
            r"\bdeep\s+learning\b",
            re.IGNORECASE,
        ),
    ),
    (
        "자동화",
        re.compile(
            r"자동화",
            re.IGNORECASE,
        ),
    ),
    (
        "지능화",
        re.compile(
            r"지능화",
            re.IGNORECASE,
        ),
    ),
    (
        "디지털기술",
        re.compile(
            r"디지털\s*기술",
            re.IGNORECASE,
        ),
    ),
]


# =========================================================
# 성과
# =========================================================

PERFORMANCE_TERMS = [
    "경영성과",
    "기업성과",
    "재무성과",
    "비재무성과",
    "생산성",
    "업무효율",
    "업무 효율",
    "효율성",
    "매출",
    "매출액",
    "수익",
    "수익성",
    "영업이익",
    "비용절감",
    "비용 절감",
    "경쟁력",
    "혁신성과",
    "혁신 성과",
    "혁신역량",
    "혁신 역량",
    "기업성장",
    "기업 성장",
    "성장성",
    "고용",
    "수출",
    "시장성과",
    "기술성과",
    "performance",
    "productivity",
    "profitability",
    "competitiveness",
    "innovation",
    "growth",
]


# =========================================================
# 공유 변수
# =========================================================

DATA_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()
SAVE_LOCK = threading.Lock()

STOP_EVENT = threading.Event()

GLOBAL_RECORDS: dict[
    tuple[str, str],
    dict[str, Any],
] = {}

SCANNED_TOTAL = 0

THREAD_LOCAL = threading.local()


# =========================================================
# 유틸
# =========================================================

def clean_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def local_name(
    tag: str,
) -> str:

    if "}" in tag:
        return tag.split("}")[-1]

    return tag


def element_text(
    elem: ET.Element,
) -> str:

    return clean_text(
        " ".join(
            elem.itertext()
        )
    )


def safe_print(
    *args,
):

    with PRINT_LOCK:
        print(*args)


def unique_list(
    values: list[str],
) -> list[str]:

    result = []
    seen = set()

    for value in values:

        value = clean_text(value)

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)

        result.append(value)

    return result


# =========================================================
# Session
# =========================================================

def get_session():

    if not hasattr(
        THREAD_LOCAL,
        "session",
    ):

        session = requests.Session()

        session.headers.update(
            {
                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64)"
            }
        )

        THREAD_LOCAL.session = session

    return THREAD_LOCAL.session


# =========================================================
# OAI 요청
# =========================================================

def request_oai(
    params: dict[str, Any],
):

    session = get_session()

    for attempt in range(1, 4):

        try:

            response = session.get(
                BASE_URL,
                params=params,
                timeout=90,
            )

            response.raise_for_status()

            root = ET.fromstring(
                response.content
            )

            for elem in root.iter():

                if (
                    local_name(elem.tag)
                    == "error"
                ):

                    raise RuntimeError(
                        element_text(elem)
                    )

            return root

        except Exception as exc:

            safe_print(
                f"[RETRY {attempt}/3]",
                exc,
            )

            if attempt == 3:
                raise

            time.sleep(
                attempt * 2
            )


# =========================================================
# metadata prefix
# =========================================================

def get_metadata_formats():

    root = request_oai(
        {
            "verb":
                "ListMetadataFormats"
        }
    )

    result = []

    for elem in root.iter():

        if (
            local_name(elem.tag)
            == "metadataPrefix"
        ):

            value = clean_text(
                elem.text
            )

            if value:
                result.append(value)

    return unique_list(result)


# =========================================================
# KCI 실제 구조 파싱
# =========================================================

def parse_record(
    record: ET.Element,
) -> dict[str, Any]:

    result = {
        "identifier": "",
        "datestamp": "",
        "article_id": "",

        "title": "",
        "title_en": "",

        "authors": [],

        "abstract": "",
        "abstract_en": "",

        "keywords": [],
        "category": "",

        "journal": "",
        "publisher": "",

        "publication_year": "",

        "language": "",

        "uci": "",
        "doi": "",

        "citation_count": "",

        "open_access": "",

        "format": "",

        "landing_url": "",

        "metadata_type": "",
    }

    # =====================================================
    # HEADER
    # =====================================================

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name == "identifier":

            if not result["identifier"]:
                result["identifier"] = (
                    element_text(elem)
                )

        elif name == "datestamp":

            if not result["datestamp"]:
                result["datestamp"] = (
                    element_text(elem)
                )

    # =====================================================
    # 어떤 metadata 형식인지 확인
    # =====================================================

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name == "oai_kci":

            result[
                "metadata_type"
            ] = "oai_kci"

            break

        if name == "dc":

            result[
                "metadata_type"
            ] = "oai_dc"

            break

    # =====================================================
    # KCI 전용 구조
    # =====================================================

    if (
        result["metadata_type"]
        == "oai_kci"
    ):

        for elem in record.iter():

            name = local_name(
                elem.tag
            )

            text = element_text(
                elem
            )

            # ---------------------------------------------
            # articleInfo ID
            # ---------------------------------------------

            if name == "articleInfo":

                article_id = (
                    elem.attrib.get(
                        "article-id",
                        "",
                    )
                )

                if article_id:

                    result[
                        "article_id"
                    ] = article_id

            if not text:
                continue

            # ---------------------------------------------
            # 제목
            # ---------------------------------------------

            if name == "article-title":

                lang = (
                    elem.attrib
                    .get(
                        "lang",
                        "",
                    )
                    .lower()
                )

                if lang == "original":

                    result[
                        "title"
                    ] = text

                elif lang == "english":

                    result[
                        "title_en"
                    ] = text

                elif not result[
                    "title"
                ]:

                    result[
                        "title"
                    ] = text

            # ---------------------------------------------
            # 초록
            # ---------------------------------------------

            elif name == "abstract":

                lang = (
                    elem.attrib
                    .get(
                        "lang",
                        "",
                    )
                    .lower()
                )

                if lang == "original":

                    result[
                        "abstract"
                    ] = text

                elif lang == "english":

                    result[
                        "abstract_en"
                    ] = text

                elif not result[
                    "abstract"
                ]:

                    result[
                        "abstract"
                    ] = text

            # ---------------------------------------------
            # 저자
            # ---------------------------------------------

            elif name == "name":

                result[
                    "authors"
                ].append(text)

            # ---------------------------------------------
            # 키워드
            # ---------------------------------------------

            elif name in {
                "keyword",
                "kwd",
            }:

                result[
                    "keywords"
                ].append(text)

            elif name == "article-categories":

                result[
                    "category"
                ] = text

            elif name == "journal-name":

                result[
                    "journal"
                ] = text

            elif name == "publisher-name":

                result[
                    "publisher"
                ] = text

            elif name == "pub-year":

                result[
                    "publication_year"
                ] = text

            elif name == "language":

                result[
                    "language"
                ] = text

            elif name == "uci":

                result[
                    "uci"
                ] = text

            elif name == "citation-count":

                result[
                    "citation_count"
                ] = text

            elif name == "orte-open-yn":

                result[
                    "open_access"
                ] = text

            elif name == "url":

                if text.startswith(
                    "http"
                ):

                    result[
                        "landing_url"
                    ] = text

    # =====================================================
    # OAI_DC 구조
    # =====================================================

    elif (
        result["metadata_type"]
        == "oai_dc"
    ):

        titles = []
        descriptions = []
        subjects = []

        for elem in record.iter():

            name = local_name(
                elem.tag
            )

            text = element_text(
                elem
            )

            if not text:
                continue

            # ---------------------------------------------
            # 제목
            # ---------------------------------------------

            if name == "title":

                lang = (
                    elem.attrib
                    .get(
                        "lang",
                        "",
                    )
                    .lower()
                )

                if lang == "original":

                    result[
                        "title"
                    ] = text

                elif lang == "english":

                    result[
                        "title_en"
                    ] = text

                else:

                    titles.append(
                        text
                    )

            # ---------------------------------------------
            # 저자
            # ---------------------------------------------

            elif name == "creator":

                # 예:
                # 홍길동(서울대); 김철수(고려대)
                parts = re.split(
                    r"[;|]",
                    text,
                )

                for part in parts:

                    part = clean_text(
                        part
                    )

                    if part:
                        result[
                            "authors"
                        ].append(
                            part
                        )

            # ---------------------------------------------
            # subject
            # ---------------------------------------------

            elif name == "subject":

                subjects.append(
                    text
                )

            # ---------------------------------------------
            # abstract
            # ---------------------------------------------

            elif name == "description":

                lang = (
                    elem.attrib
                    .get(
                        "lang",
                        "",
                    )
                    .lower()
                )

                if lang == "original":

                    result[
                        "abstract"
                    ] = text

                elif lang == "english":

                    result[
                        "abstract_en"
                    ] = text

                else:

                    descriptions.append(
                        text
                    )

            elif name == "publisher":

                result[
                    "publisher"
                ] = text

            elif name == "date":

                # 2013-05
                # 2013
                # 등 처리
                year_match = re.search(
                    r"\b(19|20)\d{2}\b",
                    text,
                )

                if year_match:

                    result[
                        "publication_year"
                    ] = (
                        year_match.group(0)
                    )

            elif name == "format":

                result[
                    "format"
                ] = text

            elif name == "language":

                result[
                    "language"
                ] = text

            elif name == "rights":

                result[
                    "open_access"
                ] = text

            elif name == "url":

                if text.startswith(
                    "http"
                ):

                    result[
                        "landing_url"
                    ] = text

            # ---------------------------------------------
            # DOI 등이 다른 필드 안에 들어오는 경우
            # ---------------------------------------------

            if "doi.org/" in text.lower():

                doi_match = re.search(
                    r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
                    text,
                    re.IGNORECASE,
                )

                if doi_match:

                    result[
                        "doi"
                    ] = (
                        doi_match
                        .group(1)
                        .rstrip(".")
                    )

        # ---------------------------------------------
        # fallback 제목
        # ---------------------------------------------

        if (
            not result["title"]
            and titles
        ):

            result["title"] = (
                titles[0]
            )

            if len(titles) > 1:

                result[
                    "title_en"
                ] = titles[1]

        # ---------------------------------------------
        # fallback abstract
        # ---------------------------------------------

        if (
            not result["abstract"]
            and descriptions
        ):

            result[
                "abstract"
            ] = descriptions[0]

            if len(
                descriptions
            ) > 1:

                result[
                    "abstract_en"
                ] = descriptions[1]

        # ---------------------------------------------
        # subject
        # ---------------------------------------------

        result[
            "keywords"
        ] = subjects

        if subjects:

            result[
                "category"
            ] = subjects[0]

        # ---------------------------------------------
        # article ID를 URL에서 추출
        # ---------------------------------------------

        if result[
            "landing_url"
        ]:

            match = re.search(
                r"artiId="
                r"(ART\d+)",
                result[
                    "landing_url"
                ],
                re.IGNORECASE,
            )

            if match:

                result[
                    "article_id"
                ] = match.group(1)

    # =====================================================
    # 공통 정리
    # =====================================================

    result[
        "authors"
    ] = unique_list(
        result[
            "authors"
        ]
    )

    result[
        "keywords"
    ] = unique_list(
        result[
            "keywords"
        ]
    )

    return result


# =========================================================
# 키워드 검색
# =========================================================

def find_terms(
    text: str,
    terms: list[str],
):

    lower = text.lower()

    result = []

    for term in terms:

        term_lower = (
            term.lower()
        )

        # SME는 영어 약어 오탐 방지
        if term_lower in {
            "sme",
            "smes",
        }:

            pattern = re.compile(
                rf"(?<![A-Za-z])"
                rf"{re.escape(term)}"
                rf"(?![A-Za-z])",
                re.IGNORECASE,
            )

            if pattern.search(text):
                result.append(term)

        elif term_lower in lower:

            result.append(term)

    return unique_list(result)


def find_tech_terms(
    text: str,
):

    result = []

    for label, pattern in (
        TECH_PATTERNS
    ):

        if pattern.search(text):

            result.append(label)

    return unique_list(result)


# =========================================================
# 관련성
# =========================================================

def calculate_relevance(
    record: dict[str, Any],
):

    searchable = " ".join(
        [
            record.get(
                "title",
                "",
            ),
            record.get(
                "title_en",
                "",
            ),
            record.get(
                "abstract",
                "",
            ),
            record.get(
                "abstract_en",
                "",
            ),
            " ".join(
                record.get(
                    "keywords",
                    [],
                )
            ),
            record.get(
                "category",
                "",
            ),
        ]
    )

    sme_matches = find_terms(
        searchable,
        SME_TERMS,
    )

    tech_matches = (
        find_tech_terms(
            searchable
        )
    )

    performance_matches = (
        find_terms(
            searchable,
            PERFORMANCE_TERMS,
        )
    )

    title_text = (
        record.get(
            "title",
            ""
        )
        + " "
        + record.get(
            "title_en",
            ""
        )
    )

    title_sme = find_terms(
        title_text,
        SME_TERMS,
    )

    title_tech = find_tech_terms(
        title_text
    )

    title_perf = find_terms(
        title_text,
        PERFORMANCE_TERMS,
    )

    score = 0

    if sme_matches:
        score += 5

    if tech_matches:
        score += 5

    if performance_matches:
        score += 2

    if title_sme:
        score += 4

    if title_tech:
        score += 4

    if title_perf:
        score += 2

    if (
        sme_matches
        and tech_matches
        and performance_matches
    ):

        relevance = "core"

    elif (
        sme_matches
        and tech_matches
    ):

        relevance = "high"

    else:

        relevance = "reject"

    record[
        "relevance"
    ] = relevance

    record[
        "relevance_score"
    ] = score

    record[
        "sme_matches"
    ] = sme_matches

    record[
        "tech_matches"
    ] = tech_matches

    record[
        "performance_matches"
    ] = performance_matches

    return record


# =========================================================
# 제목 정규화
# =========================================================

def normalize_title(
    title: str,
):

    title = (
        clean_text(title)
        .lower()
    )

    return re.sub(
        r"[^0-9a-z가-힣]+",
        "",
        title,
    )


def make_key(
    record,
):

    article_id = clean_text(
        record.get(
            "article_id",
            "",
        )
    )

    if article_id:

        return (
            "article_id",
            article_id,
        )

    identifier = clean_text(
        record.get(
            "identifier",
            "",
        )
    )

    if identifier:

        return (
            "identifier",
            identifier,
        )

    return (
        "title",
        normalize_title(
            record.get(
                "title",
                "",
            )
        ),
    )


def exists_locked(
    record,
):

    key = make_key(
        record
    )

    if key in GLOBAL_RECORDS:
        return True

    new_title = normalize_title(
        record.get(
            "title",
            "",
        )
    )

    if not new_title:
        return True

    for existing in (
        GLOBAL_RECORDS.values()
    ):

        old_title = normalize_title(
            existing.get(
                "title",
                "",
            )
        )

        if (
            new_title
            == old_title
        ):

            return True

    return False


# =========================================================
# 저장
# =========================================================

def save_snapshot():

    with DATA_LOCK:

        records = list(
            GLOBAL_RECORDS.values()
        )

    records.sort(
        key=lambda r: (
            int(
                r.get(
                    "relevance_score",
                    0,
                )
            ),
            str(
                r.get(
                    "publication_year",
                    "",
                )
            ),
        ),
        reverse=True,
    )

    with SAVE_LOCK:

        with JSON_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                records,
                f,
                ensure_ascii=False,
                indent=2,
            )

        with CSV_FILE.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            writer = csv.writer(f)

            writer.writerow(
                [
                    "article_id",
                    "identifier",
                    "title",
                    "title_en",
                    "publication_year",
                    "journal",
                    "publisher",
                    "authors",
                    "category",
                    "keywords",
                    "relevance",
                    "score",
                    "sme_matches",
                    "tech_matches",
                    "performance_matches",
                    "open_access",
                    "citation_count",
                    "uci",
                    "landing_url",
                    "abstract",
                    "abstract_en",
                    "datestamp",
                ]
            )

            for r in records:

                writer.writerow(
                    [
                        r.get(
                            "article_id",
                            "",
                        ),
                        r.get(
                            "identifier",
                            "",
                        ),
                        r.get(
                            "title",
                            "",
                        ),
                        r.get(
                            "title_en",
                            "",
                        ),
                        r.get(
                            "publication_year",
                            "",
                        ),
                        r.get(
                            "journal",
                            "",
                        ),
                        r.get(
                            "publisher",
                            "",
                        ),
                        " | ".join(
                            r.get(
                                "authors",
                                [],
                            )
                        ),
                        r.get(
                            "category",
                            "",
                        ),
                        " | ".join(
                            r.get(
                                "keywords",
                                [],
                            )
                        ),
                        r.get(
                            "relevance",
                            "",
                        ),
                        r.get(
                            "relevance_score",
                            0,
                        ),
                        " | ".join(
                            r.get(
                                "sme_matches",
                                [],
                            )
                        ),
                        " | ".join(
                            r.get(
                                "tech_matches",
                                [],
                            )
                        ),
                        " | ".join(
                            r.get(
                                "performance_matches",
                                [],
                            )
                        ),
                        r.get(
                            "open_access",
                            "",
                        ),
                        r.get(
                            "citation_count",
                            "",
                        ),
                        r.get(
                            "uci",
                            "",
                        ),
                        r.get(
                            "landing_url",
                            "",
                        ),
                        r.get(
                            "abstract",
                            "",
                        ),
                        r.get(
                            "abstract_en",
                            "",
                        ),
                        r.get(
                            "datestamp",
                            "",
                        ),
                    ]
                )


# =========================================================
# 기존 데이터
# =========================================================

def load_existing():

    if not JSON_FILE.exists():

        safe_print(
            "[EXISTING] 기존 데이터 없음"
        )

        return

    try:

        with JSON_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            records = json.load(f)

    except Exception:

        return

    accepted = 0

    for record in records:

        record = (
            calculate_relevance(
                record
            )
        )

        if (
            record[
                "relevance"
            ]
            == "reject"
        ):
            continue

        with DATA_LOCK:

            if exists_locked(record):
                continue

            GLOBAL_RECORDS[
                make_key(record)
            ] = record

            accepted += 1

    safe_print(
        f"[EXISTING] "
        f"{accepted}편 불러옴"
    )


# =========================================================
# 기간별 병렬 수집
# =========================================================

def collect_range(
    prefix: str,
    start_date: str,
    end_date: str,
):

    global SCANNED_TOTAL

    range_name = (
        f"{start_date} ~ {end_date}"
    )

    safe_print(
        f"[START] {range_name}"
    )

    params = {
        "verb":
            "ListRecords",
        "metadataPrefix":
            prefix,
        "from":
            start_date,
        "until":
            end_date,
    }

    page = 1
    scanned = 0
    added = 0

    while not STOP_EVENT.is_set():

        root = request_oai(
            params
        )

        page_records = [
            elem
            for elem in root.iter()
            if (
                local_name(elem.tag)
                == "record"
            )
        ]

        if not page_records:
            break

        for elem in page_records:

            if STOP_EVENT.is_set():
                break

            scanned += 1

            with DATA_LOCK:
                SCANNED_TOTAL += 1

            record = parse_record(
                elem
            )

            # 이제 실제 article-title이 들어옴
            if not record["title"]:
                continue

            record = (
                calculate_relevance(
                    record
                )
            )

            if (
                record["relevance"]
                == "reject"
            ):
                continue

            with DATA_LOCK:

                if exists_locked(
                    record
                ):
                    continue

                GLOBAL_RECORDS[
                    make_key(record)
                ] = record

                added += 1

                total = len(
                    GLOBAL_RECORDS
                )

            safe_print(
                f"[MATCH] "
                f"[{record['relevance']}] "
                f"{record['publication_year']} | "
                f"{record['title'][:90]}"
            )

            safe_print(
                f"        SME : "
                f"{', '.join(record['sme_matches'])}"
            )

            safe_print(
                f"        TECH: "
                f"{', '.join(record['tech_matches'])}"
            )

            if (
                record[
                    "performance_matches"
                ]
            ):

                safe_print(
                    f"        PERF: "
                    f"{', '.join(record['performance_matches'])}"
                )

            safe_print(
                f"        OA  : "
                f"{record['open_access']}"
            )

            safe_print(
                f"        TOTAL: "
                f"{total}/{TARGET_RELEVANT}"
            )

            if total % 25 == 0:
                save_snapshot()

            if (
                total
                >= TARGET_RELEVANT
            ):

                STOP_EVENT.set()
                break

        safe_print(
            f"[{range_name}] "
            f"page={page} "
            f"scanned={scanned:,} "
            f"added={added:,}"
        )

        if STOP_EVENT.is_set():
            break

        token = ""

        for elem in root.iter():

            if (
                local_name(elem.tag)
                == "resumptionToken"
            ):

                token = clean_text(
                    elem.text
                )

                break

        if not token:
            break

        params = {
            "verb":
                "ListRecords",
            "resumptionToken":
                token,
        }

        page += 1

        if REQUEST_SLEEP:
            time.sleep(
                REQUEST_SLEEP
            )

    safe_print(
        f"[DONE] "
        f"{range_name} "
        f"scanned={scanned:,}, "
        f"added={added:,}"
    )

    return {
        "range": range_name,
        "scanned": scanned,
        "added": added,
    }


# =========================================================
# 최종 요약
# =========================================================

def print_summary():

    with DATA_LOCK:

        records = list(
            GLOBAL_RECORDS.values()
        )

        scanned = (
            SCANNED_TOTAL
        )

    core = [
        r
        for r in records
        if r["relevance"] == "core"
    ]

    high = [
        r
        for r in records
        if r["relevance"] == "high"
    ]

    oa = [
        r
        for r in records
        if (
            str(
                r.get(
                    "open_access",
                    "",
                )
            )
            .upper()
            == "Y"
        )
    ]

    records.sort(
        key=lambda r:
            r.get(
                "relevance_score",
                0,
            ),
        reverse=True,
    )

    print()
    print("=" * 90)
    print("[FINAL SUMMARY]")

    print(
        f"이번 실행 검사량    : "
        f"{scanned:,}"
    )

    print(
        f"관련 논문 후보      : "
        f"{len(records):,}"
    )

    print(
        f"core               : "
        f"{len(core):,}"
    )

    print(
        f"high               : "
        f"{len(high):,}"
    )

    print(
        f"원문공개 표시(Y)    : "
        f"{len(oa):,}"
    )

    print("=" * 90)

    print()
    print("[TOP SAMPLE]")

    for i, r in enumerate(
        records[:30],
        1,
    ):

        print(
            f"{i:02d}. "
            f"[{r['relevance']}] "
            f"score={r['relevance_score']} "
            f"{r['publication_year']} "
            f"{r['title']}"
        )


# =========================================================
# main
# =========================================================

def main():

    print()
    print("=" * 90)
    print(
        "KCI 중소기업 + AI/DX "
        "관련 논문 메타데이터 수집"
    )
    print("=" * 90)

    load_existing()

    prefixes = (
        get_metadata_formats()
    )

    print(
        "\n[METADATA PREFIXES]"
    )

    for p in prefixes:
        print(" -", p)

    if "oai_kci" not in prefixes:

        raise RuntimeError(
            "oai_kci를 사용할 수 없습니다."
        )

    prefix = "oai_kci"

    print(
        "\n[SELECTED]",
        prefix,
    )

    print(
        f"[MAX WORKERS] "
        f"{MAX_WORKERS}"
    )

    print(
        f"[TARGET] "
        f"{TARGET_RELEVANT}"
    )

    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                collect_range,
                prefix,
                start,
                end,
            )
            for start, end
            in DATE_RANGES
        ]

        for future in as_completed(
            futures
        ):

            try:

                results.append(
                    future.result()
                )

            except Exception as exc:

                safe_print(
                    "[WORKER ERROR]",
                    exc,
                )

    save_snapshot()

    print()
    print("[WORKER RESULTS]")

    for result in results:

        print(
            result
        )

    print_summary()

    print()
    print(
        "[SAVED]",
        JSON_FILE,
    )

    print(
        "[SAVED]",
        CSV_FILE,
    )


if __name__ == "__main__":
    main()