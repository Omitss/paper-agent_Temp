from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
TEXT_DIR = DATA_DIR / "text"
META_DIR = DATA_DIR / "metadata"

EXTRACTED_FILE = META_DIR / "papers_extracted.jsonl"
KCI_RELEVANT_JSON = META_DIR / "kci_sme_relevant.json"
KCI_RELEVANT_CSV = META_DIR / "kci_sme_relevant.csv"

OUTPUT_FILE = META_DIR / "papers_resolved.jsonl"
REVIEW_FILE = META_DIR / "papers_metadata_review.jsonl"


# ============================================================
# 기본 함수
# ============================================================

def clean(value: Any) -> str:
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\x00", "")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_title(value: str) -> str:
    value = clean(value)
    value = unicodedata.normalize("NFKC", value)
    value = value.lower()

    # 비교용이므로 공백/특수문자 제거
    value = re.sub(
        r"[^0-9a-z가-힣]",
        "",
        value,
    )

    return value


def normalize_filename_title(value: str) -> str:
    value = clean(value)

    # 파일명 끝의 번호/다운로드 표시 제거
    value = re.sub(
        r"\s*\(\d+\)\s*$",
        "",
        value,
    )

    value = re.sub(
        r"\s*-\s*복사본\s*$",
        "",
        value,
        flags=re.I,
    )

    return value.strip(" _-.")


def read_jsonl(path: Path) -> list[dict]:
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    return rows


def write_jsonl(
    path: Path,
    rows: list[dict],
) -> None:

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
# 기존 KCI relevant 데이터 읽기
# ============================================================

def flatten_records(obj: Any) -> list[dict]:
    """
    JSON 구조가
    list이든
    {"records": [...]}
    {"items": [...]}
    형태든 최대한 대응.
    """

    if isinstance(obj, list):
        return [
            x for x in obj
            if isinstance(x, dict)
        ]

    if isinstance(obj, dict):

        for key in (
            "records",
            "items",
            "papers",
            "results",
            "data",
        ):
            value = obj.get(key)

            if isinstance(value, list):
                return [
                    x for x in value
                    if isinstance(x, dict)
                ]

        # 단일 record일 가능성
        return [obj]

    return []


def load_kci_records() -> list[dict]:
    records: list[dict] = []

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    if KCI_RELEVANT_JSON.exists():

        try:
            with KCI_RELEVANT_JSON.open(
                "r",
                encoding="utf-8",
            ) as f:
                obj = json.load(f)

            records.extend(
                flatten_records(obj)
            )

        except Exception as e:
            print(
                f"[WARN] kci_sme_relevant.json "
                f"읽기 실패: {e}"
            )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if KCI_RELEVANT_CSV.exists():

        try:
            with KCI_RELEVANT_CSV.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as f:

                reader = csv.DictReader(f)

                for row in reader:
                    records.append(dict(row))

        except Exception as e:
            print(
                f"[WARN] kci_sme_relevant.csv "
                f"읽기 실패: {e}"
            )

    return records


# ============================================================
# dict에서 다양한 필드명 찾기
# ============================================================

def first_value(
    row: dict,
    keys: tuple[str, ...],
) -> str:

    lower_map = {
        str(k).lower(): v
        for k, v in row.items()
    }

    for key in keys:

        if key in row:
            value = clean(row[key])

            if value:
                return value

        value = clean(
            lower_map.get(key.lower())
        )

        if value:
            return value

    return ""


TITLE_KEYS = (
    "title",
    "article_title",
    "paper_title",
    "논문명",
    "제목",
)

AUTHOR_KEYS = (
    "author",
    "authors",
    "creator",
    "저자",
)

YEAR_KEYS = (
    "year",
    "published_year",
    "publication_year",
    "발행년도",
    "발행연도",
    "date",
)

DOI_KEYS = (
    "doi",
    "DOI",
)

KCI_KEYS = (
    "kci_id",
    "kciId",
    "article_id",
    "identifier",
    "id",
)

JOURNAL_KEYS = (
    "journal",
    "journal_name",
    "publisher",
    "학술지",
    "학술지명",
)


# ============================================================
# PDF metadata 값 검증
# ============================================================

BAD_PDF_TITLE_PATTERNS = (
    "microsoft word",
    "hwp",
    "한글",
    "untitled",
    "document",
    "acrobat",
    "pdf",
)


def valid_pdf_title(title: str) -> bool:
    title = clean(title)

    if len(title) < 8:
        return False

    low = title.lower()

    if any(
        bad in low
        for bad in BAD_PDF_TITLE_PATTERNS
    ):
        return False

    # 파일 경로나 프로그램명
    if "\\" in title:
        return False

    if title.lower().endswith(".hwp"):
        return False

    if title.lower().endswith(".docx"):
        return False

    return True


# ============================================================
# 본문에서 DOI / 연도 등 안전한 값 추출
# ============================================================

DOI_RE = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b",
    re.I,
)

YEAR_RE = re.compile(
    r"(?<!\d)(19\d{2}|20\d{2})(?!\d)"
)

KCI_RE = re.compile(
    r"\bART\d{6,}\b",
    re.I,
)


def extract_safe_identifiers(
    text: str,
) -> dict[str, Any]:

    # 메타데이터에는 앞부분만 필요
    head = text[:30000]

    doi_match = DOI_RE.search(head)
    kci_match = KCI_RE.search(head)

    years = YEAR_RE.findall(
        head[:15000]
    )

    year = None

    if years:
        counts = Counter(years)

        # 지나치게 과거인 참고문헌 연도보다
        # 앞부분에서 자주 등장하는 연도 후보
        candidates = [
            int(y)
            for y, _ in counts.most_common()
            if 1980 <= int(y) <= 2030
        ]

        if candidates:
            year = candidates[0]

    return {
        "doi": (
            doi_match.group(0).rstrip(".,;)")
            if doi_match
            else None
        ),
        "kci_id": (
            kci_match.group(0).upper()
            if kci_match
            else None
        ),
        "year_candidate": year,
    }


# ============================================================
# 문서 유형
# ============================================================

def detect_document_type(
    text: str,
) -> str:

    head = text[:20000]

    if re.search(
        r"박사\s*학위\s*논문|"
        r"박사학위논문",
        head,
    ):
        return "doctoral_thesis"

    if re.search(
        r"석사\s*학위\s*논문|"
        r"석사학위논문",
        head,
    ):
        return "master_thesis"

    if (
        "학위논문" in head
        and "대학원" in head
    ):
        return "thesis"

    if re.search(
        r"연구보고서|정책보고서|"
        r"정책연구|연구 보고서",
        head,
    ):
        return "report"

    if re.search(
        r"Abstract|초록|국문초록|"
        r"국문요약|Keywords|주제어",
        head,
        re.I,
    ):
        return "journal_article"

    return "unknown"


# ============================================================
# KCI 제목 index
# ============================================================

def build_kci_index(
    records: list[dict],
) -> list[dict]:

    output = []
    seen = set()

    for row in records:

        title = first_value(
            row,
            TITLE_KEYS,
        )

        if not title:
            continue

        norm = normalize_title(title)

        if len(norm) < 5:
            continue

        # JSON + CSV 중복 방지
        signature = (
            norm,
            first_value(row, AUTHOR_KEYS),
        )

        if signature in seen:
            continue

        seen.add(signature)

        output.append(
            {
                "title": title,
                "norm_title": norm,
                "authors": first_value(
                    row,
                    AUTHOR_KEYS,
                ),
                "year": first_value(
                    row,
                    YEAR_KEYS,
                ),
                "doi": first_value(
                    row,
                    DOI_KEYS,
                ),
                "kci_id": first_value(
                    row,
                    KCI_KEYS,
                ),
                "journal": first_value(
                    row,
                    JOURNAL_KEYS,
                ),
                "raw": row,
            }
        )

    return output


# ============================================================
# 제목 비교
# ============================================================

def similarity(
    a: str,
    b: str,
) -> float:

    a = normalize_title(a)
    b = normalize_title(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    # 한쪽이 다른 쪽을 거의 완전히 포함
    shorter = min(
        len(a),
        len(b),
    )

    longer = max(
        len(a),
        len(b),
    )

    if shorter >= 10 and (
        a in b or b in a
    ):
        return shorter / longer

    # character bigram Jaccard
    def grams(text: str) -> set[str]:
        if len(text) < 2:
            return {text}

        return {
            text[i:i + 2]
            for i in range(len(text) - 1)
        }

    ga = grams(a)
    gb = grams(b)

    if not ga or not gb:
        return 0.0

    return (
        len(ga & gb)
        / len(ga | gb)
    )


def find_best_kci_match(
    candidates: list[str],
    kci_index: list[dict],
) -> tuple[dict | None, float]:

    best = None
    best_score = 0.0

    for candidate in candidates:

        if not candidate:
            continue

        for item in kci_index:

            score = similarity(
                candidate,
                item["title"],
            )

            if score > best_score:
                best_score = score
                best = item

    return best, best_score


# ============================================================
# TXT 안에 실제 제목이 존재하는지 확인
# ============================================================

def title_present_in_text(
    title: str,
    text: str,
) -> bool:

    if not title:
        return False

    # 앞 30,000자에서 비교
    head = text[:30000]

    normalized_title = normalize_title(
        title
    )

    normalized_head = normalize_title(
        head
    )

    if len(normalized_title) < 8:
        return False

    return normalized_title in normalized_head


# ============================================================
# 연도 정리
# ============================================================

def parse_year(value: Any) -> int | None:
    value = clean(value)

    match = YEAR_RE.search(value)

    if not match:
        return None

    year = int(match.group(1))

    if 1980 <= year <= 2030:
        return year

    return None


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 72)
    print("논문 Metadata 자동 확정")
    print("=" * 72)

    extracted = read_jsonl(
        EXTRACTED_FILE
    )

    kci_records = load_kci_records()
    kci_index = build_kci_index(
        kci_records
    )

    print(
        f"처리 대상             : "
        f"{len(extracted)}"
    )

    print(
        f"KCI 관련 metadata     : "
        f"{len(kci_index)}"
    )

    print()

    resolved_rows = []
    review_rows = []

    counts = Counter()

    for index, row in enumerate(
        extracted,
        start=1,
    ):

        paper_id = row["paper_id"]

        source_filename = row[
            "source_filename"
        ]

        print(
            f"[{index}/{len(extracted)}] "
            f"{paper_id} | {source_filename}"
        )

        text_file = PROJECT_ROOT / row[
            "text_file"
        ]

        if not text_file.exists():

            new_row = dict(row)

            new_row["metadata_status"] = (
                "REVIEW"
            )

            new_row["review_reason"] = (
                "TEXT_FILE_NOT_FOUND"
            )

            resolved_rows.append(new_row)
            review_rows.append(new_row)

            counts["REVIEW"] += 1

            print(
                "    REVIEW : TXT 없음"
            )

            continue

        text = text_file.read_text(
            encoding="utf-8",
            errors="replace",
        )

        candidates = row.get(
            "title_candidates",
            {},
        )

        filename_title = (
            candidates.get("filename")
            if isinstance(candidates, dict)
            else None
        )

        if filename_title:
            filename_title = (
                normalize_filename_title(
                    filename_title
                )
            )

        pdf_title = (
            candidates.get(
                "pdf_metadata"
            )
            if isinstance(candidates, dict)
            else None
        )

        if pdf_title and not valid_pdf_title(
            pdf_title
        ):
            pdf_title = None

        title_candidates = [
            x
            for x in (
                filename_title,
                pdf_title,
            )
            if x
        ]

        # ----------------------------------------------------
        # 기존 KCI metadata와 비교
        # ----------------------------------------------------

        kci_match, kci_score = (
            find_best_kci_match(
                title_candidates,
                kci_index,
            )
        )

        # ----------------------------------------------------
        # DOI / KCI ID / 연도 후보
        # ----------------------------------------------------

        safe_ids = extract_safe_identifiers(
            text
        )

        document_type = (
            detect_document_type(text)
        )

        # ----------------------------------------------------
        # 제목 결정
        # ----------------------------------------------------

        title = None
        title_source = None
        confidence = "REVIEW"
        confidence_score = 0.0

        # 1. KCI metadata와 매우 높은 일치
        if (
            kci_match
            and kci_score >= 0.92
            and title_present_in_text(
                kci_match["title"],
                text,
            )
        ):
            title = kci_match["title"]
            title_source = "KCI_METADATA"
            confidence = "HIGH"
            confidence_score = kci_score

        # 2. 파일명 제목 + PDF metadata 제목 일치
        elif (
            filename_title
            and pdf_title
            and similarity(
                filename_title,
                pdf_title,
            ) >= 0.92
            and title_present_in_text(
                filename_title,
                text,
            )
        ):
            # 보통 사람이 저장한 파일명이 더 깔끔
            title = filename_title
            title_source = (
                "FILENAME_AND_PDF_METADATA"
            )
            confidence = "HIGH"
            confidence_score = similarity(
                filename_title,
                pdf_title,
            )

        # 3. 제목형 파일명이고 본문에도 정확히 존재
        elif (
            filename_title
            and len(
                normalize_title(
                    filename_title
                )
            ) >= 12
            and title_present_in_text(
                filename_title,
                text,
            )
        ):
            title = filename_title
            title_source = "FILENAME"
            confidence = "HIGH"
            confidence_score = 0.95

        # 4. PDF metadata 제목이 본문에 존재
        elif (
            pdf_title
            and len(
                normalize_title(
                    pdf_title
                )
            ) >= 12
            and title_present_in_text(
                pdf_title,
                text,
            )
        ):
            title = pdf_title
            title_source = "PDF_METADATA"
            confidence = "HIGH"
            confidence_score = 0.93

        # 5. KCI metadata가 꽤 유사
        elif (
            kci_match
            and kci_score >= 0.82
            and title_present_in_text(
                kci_match["title"],
                text,
            )
        ):
            title = kci_match["title"]
            title_source = "KCI_METADATA"
            confidence = "MEDIUM"
            confidence_score = kci_score

        # ----------------------------------------------------
        # 저자/연도/DOI 등
        # ----------------------------------------------------

        authors = None
        year = None
        doi = safe_ids["doi"]
        kci_id = safe_ids["kci_id"]
        journal = None

        if kci_match and (
            confidence in (
                "HIGH",
                "MEDIUM",
            )
        ):
            authors = (
                kci_match["authors"]
                or None
            )

            year = parse_year(
                kci_match["year"]
            )

            doi = (
                kci_match["doi"]
                or doi
            )

            kci_id = (
                kci_match["kci_id"]
                or kci_id
            )

            journal = (
                kci_match["journal"]
                or None
            )

        if year is None:
            year = safe_ids[
                "year_candidate"
            ]

        # PDF author는 KCI 저자가 없을 때만
        if not authors:
            pdf_meta = row.get(
                "pdf_metadata",
                {},
            )

            pdf_author = clean(
                pdf_meta.get("author")
                if isinstance(
                    pdf_meta,
                    dict,
                )
                else ""
            )

            if (
                pdf_author
                and len(pdf_author) <= 150
            ):
                authors = pdf_author

        # ----------------------------------------------------
        # 결과
        # ----------------------------------------------------

        new_row = dict(row)

        new_row.update(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "kci_id": kci_id,
                "journal": journal,
                "document_type": (
                    document_type
                ),
                "metadata_status": (
                    confidence
                ),
                "metadata_confidence": (
                    round(
                        confidence_score,
                        4,
                    )
                ),
                "title_source": (
                    title_source
                ),
                "kci_match_title": (
                    kci_match["title"]
                    if kci_match
                    else None
                ),
                "kci_match_score": (
                    round(kci_score, 4)
                ),
            }
        )

        # ----------------------------------------------------
        # REVIEW 이유
        # ----------------------------------------------------

        if confidence == "REVIEW":

            reasons = []

            if not filename_title:
                reasons.append(
                    "NO_FILENAME_TITLE"
                )

            if not pdf_title:
                reasons.append(
                    "NO_VALID_PDF_TITLE"
                )

            if (
                not kci_match
                or kci_score < 0.82
            ):
                reasons.append(
                    "NO_STRONG_KCI_MATCH"
                )

            new_row["review_reason"] = (
                reasons
            )

            review_rows.append(new_row)

        resolved_rows.append(new_row)

        counts[confidence] += 1

        print(
            f"    {confidence:<6}"
            f" | TYPE={document_type}"
        )

        if title:
            print(
                f"    TITLE : "
                f"{title[:100]}"
            )

        elif kci_match:
            print(
                f"    KCI?  : "
                f"{kci_match['title'][:100]}"
                f" ({kci_score:.3f})"
            )

    # ========================================================
    # 저장
    # ========================================================

    write_jsonl(
        OUTPUT_FILE,
        resolved_rows,
    )

    write_jsonl(
        REVIEW_FILE,
        review_rows,
    )

    print()
    print("=" * 72)
    print("Metadata 1차 확정 완료")
    print("=" * 72)

    print(
        f"HIGH              : "
        f"{counts['HIGH']}"
    )

    print(
        f"MEDIUM            : "
        f"{counts['MEDIUM']}"
    )

    print(
        f"REVIEW            : "
        f"{counts['REVIEW']}"
    )

    print(
        f"TOTAL             : "
        f"{len(resolved_rows)}"
    )

    print()
    print(
        f"전체 결과:\n{OUTPUT_FILE}"
    )

    print()
    print(
        f"추가 판별 필요:\n{REVIEW_FILE}"
    )

    print()
    print(
        "※ HIGH만 자동 확정으로 간주합니다."
    )

    print(
        "※ MEDIUM/REVIEW는 다음 단계에서 "
        "PDF 앞부분 기반으로 재판별합니다."
    )


if __name__ == "__main__":
    main()