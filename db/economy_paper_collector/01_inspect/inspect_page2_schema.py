import requests
import xml.etree.ElementTree as ET


BASE_URL = "https://open.kci.go.kr/oai/request"


def local_name(tag):
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


def clean(text):
    if not text:
        return ""

    return " ".join(text.split())


# =========================================================
# PAGE 1
# =========================================================

params = {
    "verb": "ListRecords",
    "metadataPrefix": "oai_kci",
    "from": "2024-01-01",
    "until": "2026-09-14",
}

response = requests.get(
    BASE_URL,
    params=params,
    timeout=90,
)

response.raise_for_status()

root = ET.fromstring(
    response.content
)

token = ""

for elem in root.iter():

    if local_name(elem.tag) == "resumptionToken":
        token = clean(elem.text)
        break


print("=" * 100)
print("[PAGE 1 TOKEN]")
print(token)
print("=" * 100)


# =========================================================
# PAGE 2
# =========================================================

response = requests.get(
    BASE_URL,
    params={
        "verb": "ListRecords",
        "resumptionToken": token,
    },
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

print()
print("PAGE 2 records:", len(records))
print()


if not records:
    raise SystemExit(
        "PAGE 2 record 없음"
    )


record = records[0]


print("=" * 100)
print("[PAGE 2 첫 번째 RECORD - 모든 TAG]")
print("=" * 100)


seen = set()

for elem in record.iter():

    name = local_name(
        elem.tag
    )

    if name in seen:
        continue

    seen.add(name)

    text = clean(
        " ".join(
            elem.itertext()
        )
    )

    if len(text) > 250:
        text = text[:250] + " ..."

    print()
    print("TAG :", name)

    if elem.attrib:
        print(
            "ATTR:",
            elem.attrib,
        )

    if text:
        print(
            "TEXT:",
            text,
        )


print()
print("=" * 100)
print("[METADATA 바로 아래 구조]")
print("=" * 100)


for elem in record.iter():

    if local_name(elem.tag) != "metadata":
        continue

    for child in list(elem):

        print(
            "metadata child:",
            local_name(child.tag),
        )

        print(
            "full tag:",
            child.tag,
        )

        print(
            "attributes:",
            child.attrib,
        )

    break