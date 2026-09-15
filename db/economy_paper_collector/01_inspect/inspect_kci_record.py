import requests
import xml.etree.ElementTree as ET


BASE_URL = "https://open.kci.go.kr/oai/request"


params = {
    "verb": "ListRecords",
    "metadataPrefix": "oai_kci",
    "from": "2024-01-01",
    "until": "2026-09-14",
}


response = requests.get(
    BASE_URL,
    params=params,
    timeout=60,
)

response.raise_for_status()

print("HTTP:", response.status_code)
print("URL:", response.url)
print()


root = ET.fromstring(response.content)


def local_name(tag):
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


record = None

for elem in root.iter():
    if local_name(elem.tag) == "record":
        record = elem
        break


if record is None:
    print("record를 찾지 못했습니다.")
    raise SystemExit


print("=" * 100)
print("첫 번째 oai_kci RECORD 구조")
print("=" * 100)


for elem in record.iter():

    name = local_name(elem.tag)

    text = " ".join(
        t.strip()
        for t in elem.itertext()
        if t.strip()
    )

    if len(text) > 500:
        text = text[:500] + " ..."

    print()
    print("TAG :", name)

    if elem.attrib:
        print("ATTR:", elem.attrib)

    if text:
        print("TEXT:", text)