import requests
import xml.etree.ElementTree as ET


BASE_URL = "https://open.kci.go.kr/oai/request"

MAX_PAGES = 5


def local_name(tag):
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


def clean(text):
    if not text:
        return ""

    return " ".join(
        text.split()
    )


def get_title(record):
    for elem in record.iter():

        if local_name(elem.tag) != "article-title":
            continue

        text = clean(
            " ".join(elem.itertext())
        )

        lang = elem.attrib.get(
            "lang",
            "",
        ).lower()

        if lang == "original" and text:
            return text

    return ""


params = {
    "verb": "ListRecords",
    "metadataPrefix": "oai_kci",
    "from": "2024-01-01",
    "until": "2026-09-14",
}


for page in range(1, MAX_PAGES + 1):

    print()
    print("=" * 100)
    print(f"[PAGE {page}]")
    print("=" * 100)

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

    record_count = len(records)

    metadata_count = 0
    title_count = 0
    deleted_count = 0

    samples = []

    for record in records:

        # ------------------------------------------------
        # deleted 여부
        # ------------------------------------------------

        is_deleted = False

        for elem in record.iter():

            if local_name(elem.tag) == "header":

                if (
                    elem.attrib
                    .get("status", "")
                    .lower()
                    == "deleted"
                ):
                    is_deleted = True

                break

        if is_deleted:
            deleted_count += 1

        # ------------------------------------------------
        # metadata 존재 여부
        # ------------------------------------------------

        has_metadata = any(
            local_name(elem.tag) == "metadata"
            for elem in record.iter()
        )

        if has_metadata:
            metadata_count += 1

        # ------------------------------------------------
        # 제목
        # ------------------------------------------------

        title = get_title(record)

        if title:
            title_count += 1

            if len(samples) < 3:
                samples.append(title)

    print("records       :", record_count)
    print("metadata      :", metadata_count)
    print("titles        :", title_count)
    print("deleted       :", deleted_count)

    print()
    print("[TITLE SAMPLE]")

    for title in samples:
        print("-", title)

    # ------------------------------------------------
    # resumptionToken
    # ------------------------------------------------

    token = ""

    for elem in root.iter():

        if local_name(elem.tag) == "resumptionToken":

            token = clean(
                elem.text
            )

            print()
            print(
                "resumptionToken attrs:",
                elem.attrib,
            )

            break

    if not token:

        print()
        print("[END] resumptionToken 없음")
        break

    print(
        "token:",
        token[:100],
        "..."
        if len(token) > 100
        else "",
    )

    params = {
        "verb": "ListRecords",
        "resumptionToken": token,
    }