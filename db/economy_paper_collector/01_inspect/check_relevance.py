import re
import requests
import xml.etree.ElementTree as ET


BASE_URL = "https://open.kci.go.kr/oai/request"

MAX_RECORDS = 1000


SME_TERMS = [
    "중소기업",
    "중소 기업",
    "중소벤처",
    "중소 제조기업",
    "중소 제조업",
    "소상공인",
    "벤처기업",
    "스타트업",
]


TECH_PATTERNS = [
    re.compile(r"(?<![A-Za-z])AI(?![A-Za-z])", re.I),
    re.compile(r"인공지능", re.I),
    re.compile(r"생성형\s*AI", re.I),
    re.compile(r"artificial\s+intelligence", re.I),
    re.compile(r"디지털\s*전환", re.I),
    re.compile(r"(?<![A-Za-z])DX(?![A-Za-z])", re.I),
    re.compile(r"스마트\s*공장", re.I),
    re.compile(r"스마트\s*팩토리", re.I),
    re.compile(r"스마트\s*제조", re.I),
    re.compile(r"머신\s*러닝", re.I),
    re.compile(r"machine\s+learning", re.I),
    re.compile(r"딥\s*러닝", re.I),
    re.compile(r"자동화", re.I),
]


def local_name(tag):
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


def clean(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def element_text(elem):
    return clean(
        " ".join(elem.itertext())
    )


def get_original_title(record):

    fallback = ""

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name not in {
            "article-title",
            "title",
        }:
            continue

        text = element_text(
            elem
        )

        if not text:
            continue

        lang = (
            elem.attrib
            .get(
                "lang",
                "",
            )
            .lower()
        )

        if lang == "original":
            return text

        if not fallback:
            fallback = text

    return fallback


def get_search_text(record):

    values = []

    valid_tags = {
        "article-title",
        "title",
        "abstract",
        "description",
        "keyword",
        "kwd",
        "subject",
        "article-categories",
    }

    for elem in record.iter():

        name = local_name(
            elem.tag
        )

        if name not in valid_tags:
            continue

        text = element_text(
            elem
        )

        if text:
            values.append(
                text
            )

    return " ".join(
        values
    )


def has_sme(text):
    lower = text.lower()

    return any(
        term.lower() in lower
        for term in SME_TERMS
    )


def has_tech(text):
    return any(
        pattern.search(text)
        for pattern in TECH_PATTERNS
    )


params = {
    "verb": "ListRecords",
    "metadataPrefix": "oai_kci",
    "from": "2024-01-01",
    "until": "2026-09-14",
}


total = 0
title_ok = 0

sme_count = 0
tech_count = 0
both_count = 0

sme_samples = []
tech_samples = []
both_samples = []


while total < MAX_RECORDS:

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=90,
    )

    response.raise_for_status()

    root = ET.fromstring(
        response.content
    )

    records = [
        elem
        for elem in root.iter()
        if local_name(elem.tag) == "record"
    ]

    if not records:
        break

    for record in records:

        if total >= MAX_RECORDS:
            break

        total += 1

        title = get_original_title(
            record
        )

        search_text = get_search_text(
            record
        )

        if title:
            title_ok += 1

        sme = has_sme(
            search_text
        )

        tech = has_tech(
            search_text
        )

        if sme:
            sme_count += 1

            if len(sme_samples) < 10:
                sme_samples.append(title)

        if tech:
            tech_count += 1

            if len(tech_samples) < 10:
                tech_samples.append(title)

        if sme and tech:
            both_count += 1

            if len(both_samples) < 20:
                both_samples.append(title)

    print(
        f"[PROGRESS] "
        f"total={total} "
        f"title={title_ok} "
        f"sme={sme_count} "
        f"tech={tech_count} "
        f"both={both_count}"
    )

    token = ""

    for elem in root.iter():

        if local_name(elem.tag) == "resumptionToken":
            token = clean(elem.text)
            break

    if not token:
        break

    params = {
        "verb": "ListRecords",
        "resumptionToken": token,
    }


print()
print("=" * 80)
print("[RESULT]")
print("=" * 80)

print("검사 논문       :", total)
print("제목 파싱 성공  :", title_ok)
print("중소기업 관련   :", sme_count)
print("AI/DX 관련      :", tech_count)
print("둘 다 포함      :", both_count)

print()
print("[SME SAMPLE]")

for title in sme_samples:
    print("-", title)

print()
print("[TECH SAMPLE]")

for title in tech_samples:
    print("-", title)

print()
print("[SME + TECH SAMPLE]")

for title in both_samples:
    print("-", title)