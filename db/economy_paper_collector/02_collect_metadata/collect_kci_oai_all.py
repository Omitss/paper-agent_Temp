from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests
import xml.etree.ElementTree as ET


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

OUTPUT_FILE = (
    METADATA_DIR
    / "kci_oai_all.jsonl"
)

STATE_FILE = (
    METADATA_DIR
    / "kci_oai_state.json"
)


# =========================================================
# KCI OAI
# =========================================================

BASE_URL = (
    "https://open.kci.go.kr/oai/request"
)

METADATA_PREFIX = "oai_kci"

# 한 번 실행할 때 추가로 수집할 최대 논문 수
#
# 첫 실행:
#   최대 50,000건
#
# 다시 실행:
#   state를 읽고 그 다음부터 최대 50,000건 추가
#
BATCH_LIMIT = 50_000

REQUEST_TIMEOUT = 90

REQUEST_SLEEP = 0.05

MAX_RETRIES = 5


# =========================================================
# 공통 함수
# =========================================================

def local_name(tag: str) -> str:

    if "}" in tag:
        return tag.split("}")[-1]

    return tag


def clean_text(
    text: str | None,
) -> str:

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def element_text(
    elem: ET.Element,
) -> str:

    return clean_text(
        " ".join(
            elem.itertext()
        )
    )


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
# DOI
# =========================================================

DOI_PATTERN = re.compile(
    r"10\.\d{4,9}/"
    r"[-._;()/:A-Z0-9]+",
    re.IGNORECASE,
)


def extract_doi(
    text: str,
) -> str:

    if not text:
        return ""

    match = DOI_PATTERN.search(text)

    if not match:
        return ""

    return (
        match.group(0)
        .rstrip(".,);]")
    )


# =========================================================
# OAI header
# =========================================================

def parse_header(
    record: ET.Element,
) -> dict[str, str]:

    result = {
        "identifier": "",
        "datestamp": "",
        "set_spec": "",
        "deleted": "N",
    }

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name == "header":

            if (
                elem.attrib
                .get("status", "")
                .lower()
                == "deleted"
            ):
                result[
                    "deleted"
                ] = "Y"

        elif name == "identifier":

            if not result[
                "identifier"
            ]:
                result[
                    "identifier"
                ] = element_text(
                    elem
                )

        elif name == "datestamp":

            if not result[
                "datestamp"
            ]:
                result[
                    "datestamp"
                ] = element_text(
                    elem
                )

        elif name == "setSpec":

            if not result[
                "set_spec"
            ]:
                result[
                    "set_spec"
                ] = element_text(
                    elem
                )

    return result


# =========================================================
# 메타데이터 형식 확인
# =========================================================

def detect_metadata_type(
    record: ET.Element,
) -> str:

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name == "oai_kci":
            return "oai_kci"

        if name == "dc":
            return "oai_dc"

    return "unknown"


# =========================================================
# KCI 고유 형식 parser
# =========================================================

def parse_oai_kci(
    record: ET.Element,
) -> dict[str, Any]:

    result = {
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
        "publication_date": "",
        "language": "",
        "uci": "",
        "doi": "",
        "citation_count": "",
        "open_access": "",
        "format": "",
        "landing_url": "",
    }

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        # -----------------------------------------
        # article ID
        # -----------------------------------------

        if name == "articleInfo":

            article_id = (
                elem.attrib
                .get(
                    "article-id",
                    "",
                )
            )

            if article_id:
                result[
                    "article_id"
                ] = article_id

        text = element_text(
            elem
        )

        if not text:
            continue

        # -----------------------------------------
        # title
        # -----------------------------------------

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

        # -----------------------------------------
        # abstract
        # -----------------------------------------

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

        # -----------------------------------------
        # author
        # -----------------------------------------

        elif name == "name":

            result[
                "authors"
            ].append(text)

        # -----------------------------------------
        # keyword
        # -----------------------------------------

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

        elif name == "format":

            result[
                "format"
            ] = text

        elif name == "url":

            if text.startswith(
                "http"
            ):
                result[
                    "landing_url"
                ] = text

        # -----------------------------------------
        # DOI 발견
        # -----------------------------------------

        if (
            not result["doi"]
            and "10." in text
        ):

            doi = extract_doi(
                text
            )

            if doi:
                result[
                    "doi"
                ] = doi

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
# Dublin Core parser
# =========================================================

def parse_oai_dc(
    record: ET.Element,
) -> dict[str, Any]:

    result = {
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
        "publication_date": "",
        "language": "",
        "uci": "",
        "doi": "",
        "citation_count": "",
        "open_access": "",
        "format": "",
        "landing_url": "",
    }

    fallback_titles = []
    fallback_descriptions = []

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        text = element_text(
            elem
        )

        if not text:
            continue

        # -----------------------------------------
        # title
        # -----------------------------------------

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

                fallback_titles.append(
                    text
                )

        # -----------------------------------------
        # author
        # -----------------------------------------

        elif name == "creator":

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

        # -----------------------------------------
        # subject
        # -----------------------------------------

        elif name == "subject":

            result[
                "keywords"
            ].append(text)

            if not result[
                "category"
            ]:

                result[
                    "category"
                ] = text

        # -----------------------------------------
        # description
        # -----------------------------------------

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

                fallback_descriptions.append(
                    text
                )

        elif name == "publisher":

            result[
                "publisher"
            ] = text

        elif name == "date":

            result[
                "publication_date"
            ] = text

            match = re.search(
                r"\b(?:19|20)\d{2}\b",
                text,
            )

            if match:

                result[
                    "publication_year"
                ] = match.group(0)

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

        # -----------------------------------------
        # DOI는 어느 필드에 들어와도 검색
        # -----------------------------------------

        if (
            not result["doi"]
            and "10." in text
        ):

            doi = extract_doi(
                text
            )

            if doi:

                result[
                    "doi"
                ] = doi

    # ---------------------------------------------
    # fallback
    # ---------------------------------------------

    if (
        not result["title"]
        and fallback_titles
    ):

        result[
            "title"
        ] = fallback_titles[0]

        if len(
            fallback_titles
        ) >= 2:

            result[
                "title_en"
            ] = fallback_titles[1]

    if (
        not result["abstract"]
        and fallback_descriptions
    ):

        result[
            "abstract"
        ] = fallback_descriptions[0]

        if len(
            fallback_descriptions
        ) >= 2:

            result[
                "abstract_en"
            ] = (
                fallback_descriptions[1]
            )

    # ---------------------------------------------
    # KCI article ID
    # ---------------------------------------------

    if result[
        "landing_url"
    ]:

        match = re.search(
            r"artiId=(ART\d+)",
            result[
                "landing_url"
            ],
            re.IGNORECASE,
        )

        if match:

            result[
                "article_id"
            ] = match.group(1)

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
# record parser
# =========================================================

def parse_record(
    record: ET.Element,
) -> dict[str, Any] | None:

    header = parse_header(
        record
    )

    if (
        header["deleted"]
        == "Y"
    ):
        return None

    metadata_type = (
        detect_metadata_type(
            record
        )
    )

    if (
        metadata_type
        == "oai_kci"
    ):

        body = parse_oai_kci(
            record
        )

    elif (
        metadata_type
        == "oai_dc"
    ):

        body = parse_oai_dc(
            record
        )

    else:

        return None

    result = {
        **header,
        **body,
        "metadata_type": (
            metadata_type
        ),
    }

    return result


# =========================================================
# HTTP
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "KCI-Metadata-Collector/1.0"
    ),
})


def request_xml(
    params: dict[str, str],
) -> ET.Element:

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = session.get(
                BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            return ET.fromstring(
                response.content
            )

        except Exception as exc:

            last_error = exc

            wait = attempt * 2

            print(
                f"[RETRY] "
                f"{attempt}/{MAX_RETRIES} "
                f"{exc}"
            )

            time.sleep(wait)

    raise RuntimeError(
        f"KCI 요청 실패: {last_error}"
    )


# =========================================================
# state
# =========================================================

def load_state() -> dict[str, Any]:

    if not STATE_FILE.exists():

        return {
            "resumption_token": "",
            "total_saved": 0,
            "finished": False,
        }

    try:

        with STATE_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "resumption_token": "",
            "total_saved": 0,
            "finished": False,
        }


def save_state(
    token: str,
    total_saved: int,
    finished: bool,
) -> None:

    state = {
        "resumption_token": token,
        "total_saved": total_saved,
        "finished": finished,
    }

    with STATE_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# JSONL
# =========================================================

def append_records(
    records: list[dict[str, Any]],
) -> None:

    if not records:
        return

    with OUTPUT_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:

        for item in records:

            f.write(
                json.dumps(
                    item,
                    ensure_ascii=False,
                )
            )

            f.write("\n")


# =========================================================
# token
# =========================================================

def get_resumption_token(
    root: ET.Element,
) -> str:

    for elem in root.iter():

        if (
            local_name(
                elem.tag
            )
            == "resumptionToken"
        ):

            return clean_text(
                elem.text
            )

    return ""


# =========================================================
# main
# =========================================================

def main():

    print()
    print("=" * 90)
    print("KCI OAI 전체 논문 메타데이터 수집")
    print("=" * 90)

    state = load_state()

    if state.get(
        "finished"
    ):

        print(
            "[DONE] 이미 KCI OAI 끝까지 "
            "수집된 상태입니다."
        )

        print(
            "FILE:",
            OUTPUT_FILE,
        )

        return

    previous_total = int(
        state.get(
            "total_saved",
            0,
        )
    )

    token = str(
        state.get(
            "resumption_token",
            "",
        )
        or ""
    )

    print(
        f"[EXISTING] "
        f"{previous_total:,}"
    )

    print(
        f"[BATCH LIMIT] "
        f"{BATCH_LIMIT:,}"
    )

    print(
        "[OUTPUT]",
        OUTPUT_FILE,
    )

    # ---------------------------------------------
    # 이어받기
    # ---------------------------------------------

    if token:

        print(
            "[RESUME] 저장된 "
            "resumptionToken 사용"
        )

        params = {
            "verb": "ListRecords",
            "resumptionToken": token,
        }

    else:

        print(
            "[START] 처음부터 수집"
        )

        params = {
            "verb": "ListRecords",
            "metadataPrefix": (
                METADATA_PREFIX
            ),
            "set": "ARTI",
        }

    run_saved = 0
    page = 0

    while (
        run_saved
        < BATCH_LIMIT
    ):

        page += 1

        root = request_xml(
            params
        )

        records = [
            elem
            for elem in root.iter()
            if (
                local_name(
                    elem.tag
                )
                == "record"
            )
        ]

        if not records:

            print(
                "[END] record 없음"
            )

            save_state(
                "",
                previous_total
                + run_saved,
                True,
            )

            break

        parsed_items = []

        kci_count = 0
        dc_count = 0
        unknown_count = 0

        for record in records:

            item = parse_record(
                record
            )

            if item is None:
                continue

            metadata_type = (
                item.get(
                    "metadata_type",
                    "",
                )
            )

            if (
                metadata_type
                == "oai_kci"
            ):
                kci_count += 1

            elif (
                metadata_type
                == "oai_dc"
            ):
                dc_count += 1

            else:
                unknown_count += 1

            parsed_items.append(
                item
            )

        remaining = (
            BATCH_LIMIT
            - run_saved
        )

        if (
            len(parsed_items)
            > remaining
        ):

            parsed_items = (
                parsed_items[
                    :remaining
                ]
            )

        append_records(
            parsed_items
        )

        run_saved += len(
            parsed_items
        )

        next_token = (
            get_resumption_token(
                root
            )
        )

        total = (
            previous_total
            + run_saved
        )

        print(
            f"[PAGE {page:,}] "
            f"records={len(records):,} "
            f"saved={len(parsed_items):,} "
            f"kci={kci_count:,} "
            f"dc={dc_count:,} "
            f"TOTAL={total:,}"
        )

        # -----------------------------------------
        # OAI 끝
        # -----------------------------------------

        if not next_token:

            print()
            print(
                "[COMPLETE] "
                "OAI 마지막 페이지 도달"
            )

            save_state(
                "",
                total,
                True,
            )

            break

        # -----------------------------------------
        # 다음 페이지 token 저장
        # -----------------------------------------

        token = next_token

        save_state(
            token,
            total,
            False,
        )

        params = {
            "verb": "ListRecords",
            "resumptionToken": (
                token
            ),
        }

        if (
            run_saved
            >= BATCH_LIMIT
        ):

            break

        time.sleep(
            REQUEST_SLEEP
        )

    print()
    print("=" * 90)
    print("[이번 실행 완료]")
    print("=" * 90)

    print(
        "이번 실행 저장:",
        f"{run_saved:,}",
    )

    print(
        "누적 저장:",
        f"{previous_total + run_saved:,}",
    )

    print(
        "파일:",
        OUTPUT_FILE,
    )

    print()
    print(
        "관련 논문 선별:"
    )

    print(
        r"python "
        r".\02_collect_metadata"
        r"\filter_sme_papers.py"
    )


if __name__ == "__main__":
    main()