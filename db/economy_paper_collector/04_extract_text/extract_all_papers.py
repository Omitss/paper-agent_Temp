from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pymupdf


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_DIR = PROJECT_ROOT / "data" / "pdf"
TEXT_DIR = PROJECT_ROOT / "data" / "text"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

INSPECTION_FILE = METADATA_DIR / "pdf_inspection.json"

OUTPUT_METADATA = METADATA_DIR / "papers_extracted.jsonl"
OUTPUT_REVIEW = METADATA_DIR / "papers_extract_review.jsonl"


# ============================================================
# 기본 설정
# ============================================================

TEXT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 유틸
# ============================================================

def normalize_space(text: str | None) -> str:
    if not text:
        return ""

    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            hasher.update(chunk)

    return hasher.hexdigest()


def clean_pdf_text(text: str) -> str:
    """
    이번 단계에서는 과도한 전처리를 하지 않는다.

    - NULL 제거
    - 줄 끝 공백 제거
    - 지나치게 많은 빈 줄만 축소

    실제 논문 구조 정리는 05_preprocess에서 한다.
    """

    text = text.replace("\x00", "")

    lines = []

    for line in text.splitlines():
        lines.append(line.rstrip())

    text = "\n".join(lines)

    # 빈 줄이 4개 이상 반복되는 경우 2개로 축소
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()


# ============================================================
# pdf_inspection.json 읽기
# ============================================================

def load_inspection() -> dict[str, Any]:
    if not INSPECTION_FILE.exists():
        raise FileNotFoundError(
            f"pdf_inspection.json을 찾을 수 없습니다.\n"
            f"{INSPECTION_FILE}"
        )

    with INSPECTION_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# 중복 파일명 수집
# ============================================================

def build_duplicate_map(
    inspection: dict[str, Any],
) -> dict[str, str]:
    """
    duplicate filename -> 대표 filename

    기존 inspect_pdfs.py 결과 구조가 조금 달라도
    최대한 대응하도록 작성.
    """

    duplicate_map: dict[str, str] = {}

    groups = inspection.get("duplicate_groups", [])

    if not isinstance(groups, list):
        return duplicate_map

    for group in groups:

        files = None

        if isinstance(group, dict):
            for key in (
                "files",
                "filenames",
                "members",
                "duplicates",
            ):
                value = group.get(key)

                if isinstance(value, list):
                    files = value
                    break

        elif isinstance(group, list):
            files = group

        if not files or len(files) < 2:
            continue

        filenames = []

        for item in files:

            if isinstance(item, str):
                filenames.append(Path(item).name)

            elif isinstance(item, dict):
                name = (
                    item.get("filename")
                    or item.get("file")
                    or item.get("path")
                )

                if name:
                    filenames.append(Path(name).name)

        if len(filenames) < 2:
            continue

        representative = filenames[0]

        for duplicate in filenames[1:]:
            duplicate_map[duplicate] = representative

    return duplicate_map


# ============================================================
# 파일명 자체가 제목인 경우 후보 생성
# ============================================================

NON_TITLE_FILENAME_PATTERNS = [
    r"^KCI_FI\d+$",
    r"^\d{6,}$",
    r"^\d+_\d+$",
]


def filename_title_candidate(
    pdf_path: Path,
) -> str | None:

    stem = pdf_path.stem.strip()

    # 다운로드 시간 같은 뒷부분 제거
    stem = re.sub(
        r"_20\d{12,}$",
        "",
        stem,
    )

    for pattern in NON_TITLE_FILENAME_PATTERNS:
        if re.fullmatch(pattern, stem, re.IGNORECASE):
            return None

    # 제목이라고 보기 어려운 짧은 파일명
    if len(stem) < 8:
        return None

    # 사람이 저장한 제목형 파일명 정리
    candidate = stem.replace("_", " ")
    candidate = re.sub(r"\s+", " ", candidate).strip()

    return candidate or None


# ============================================================
# PDF 내부 metadata
# ============================================================

def get_pdf_metadata(
    doc: pymupdf.Document,
) -> dict[str, str]:

    raw = doc.metadata or {}

    return {
        "title": normalize_space(raw.get("title")),
        "author": normalize_space(raw.get("author")),
        "subject": normalize_space(raw.get("subject")),
        "keywords": normalize_space(raw.get("keywords")),
        "creator": normalize_space(raw.get("creator")),
        "producer": normalize_space(raw.get("producer")),
        "creationDate": normalize_space(
            raw.get("creationDate")
        ),
        "modDate": normalize_space(
            raw.get("modDate")
        ),
    }


# ============================================================
# 전체 PDF → TXT
# ============================================================

def extract_pdf(
    pdf_path: Path,
) -> dict[str, Any]:

    result: dict[str, Any] = {
        "success": False,
        "page_count": 0,
        "text_chars": 0,
        "pdf_metadata": {},
        "error": None,
    }

    try:
        doc = pymupdf.open(pdf_path)

        result["page_count"] = len(doc)
        result["pdf_metadata"] = get_pdf_metadata(doc)

        pages = []

        for page_number in range(len(doc)):
            page = doc[page_number]

            try:
                # sort=True:
                # 가능한 경우 시각적 읽기 순서에 맞춰 추출
                text = page.get_text(
                    "text",
                    sort=True,
                )

            except Exception as e:
                text = (
                    f"\n"
                    f"[PAGE_EXTRACTION_ERROR "
                    f"page={page_number + 1}: {e}]"
                    f"\n"
                )

            # 페이지 경계를 보존
            pages.append(
                f"\n"
                f"===== PAGE {page_number + 1} =====\n"
                f"{text}"
            )

        doc.close()

        full_text = "\n".join(pages)
        full_text = clean_pdf_text(full_text)

        result["text"] = full_text
        result["text_chars"] = len(full_text)
        result["success"] = bool(full_text.strip())

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


# ============================================================
# JSONL 저장
# ============================================================

def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        for record in records:
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 70)
    print("04_extract_text")
    print("PDF 전체 TXT 추출")
    print("=" * 70)

    inspection = load_inspection()
    duplicate_map = build_duplicate_map(inspection)

    pdf_files = sorted(
        PDF_DIR.glob("*.pdf"),
        key=lambda p: p.name.lower(),
    )

    print()
    print(f"PDF 발견 : {len(pdf_files)}")
    print(
        f"inspection 중복 여분 파일 : "
        f"{len(duplicate_map)}"
    )
    print()

    records: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []

    processed_hashes: dict[str, str] = {}

    success_count = 0
    failed_count = 0
    duplicate_count = 0

    paper_number = 0

    for index, pdf_path in enumerate(
        pdf_files,
        start=1,
    ):

        print(
            f"[{index}/{len(pdf_files)}] "
            f"{pdf_path.name}"
        )

        # ----------------------------------------------------
        # SHA256 계산
        # ----------------------------------------------------

        try:
            file_hash = sha256_file(pdf_path)

        except Exception as e:

            record = {
                "source_filename": pdf_path.name,
                "status": "HASH_ERROR",
                "error": str(e),
            }

            review_records.append(record)

            print(f"    HASH ERROR : {e}")
            continue

        # ----------------------------------------------------
        # 실제 SHA256 기준으로도 중복 방지
        # ----------------------------------------------------

        if file_hash in processed_hashes:

            duplicate_count += 1

            representative = processed_hashes[file_hash]

            print(
                f"    SKIP DUPLICATE → "
                f"{representative}"
            )

            continue

        processed_hashes[file_hash] = pdf_path.name

        # ----------------------------------------------------
        # 고유 문서 번호
        # ----------------------------------------------------

        paper_number += 1

        paper_id = f"paper_{paper_number:04d}"

        # ----------------------------------------------------
        # PDF 추출
        # ----------------------------------------------------

        extraction = extract_pdf(pdf_path)

        if not extraction["success"]:

            failed_count += 1

            record = {
                "paper_id": paper_id,
                "source_filename": pdf_path.name,
                "sha256": file_hash,
                "status": "EXTRACTION_FAILED",
                "page_count": extraction["page_count"],
                "text_chars": extraction["text_chars"],
                "error": extraction["error"],
            }

            records.append(record)
            review_records.append(record)

            print(
                f"    FAILED : "
                f"{extraction['error']}"
            )

            continue

        # ----------------------------------------------------
        # TXT 저장
        # ----------------------------------------------------

        txt_filename = f"{paper_id}.txt"
        txt_path = TEXT_DIR / txt_filename

        txt_path.write_text(
            extraction["text"],
            encoding="utf-8",
        )

        # ----------------------------------------------------
        # 제목 후보
        # ----------------------------------------------------

        filename_title = filename_title_candidate(
            pdf_path
        )

        pdf_meta = extraction["pdf_metadata"]

        pdf_metadata_title = (
            pdf_meta.get("title") or None
        )

        pdf_metadata_author = (
            pdf_meta.get("author") or None
        )

        # ----------------------------------------------------
        # 현재 단계 metadata
        # ----------------------------------------------------

        record = {
            "paper_id": paper_id,

            "source_filename": pdf_path.name,

            "sha256": file_hash,

            "status": "TEXT_EXTRACTED",

            "page_count": extraction["page_count"],

            "text_chars": extraction["text_chars"],

            "text_file": str(
                Path("data")
                / "text"
                / txt_filename
            ).replace("\\", "/"),

            # 아직 제목 확정 아님
            "title": None,

            "title_candidates": {
                "filename": filename_title,
                "pdf_metadata": pdf_metadata_title,
            },

            "authors": None,
            "year": None,
            "doi": None,
            "kci_id": None,
            "journal": None,
            "institution": None,
            "document_type": None,

            "pdf_metadata": pdf_meta,

            "metadata_status": "PENDING",
        }

        records.append(record)

        success_count += 1

        print(
            f"    OK"
            f" | {extraction['page_count']} pages"
            f" | {extraction['text_chars']:,} chars"
        )

        if filename_title:
            print(
                f"    FILE TITLE? : "
                f"{filename_title[:90]}"
            )

        if pdf_metadata_title:
            print(
                f"    PDF TITLE?  : "
                f"{pdf_metadata_title[:90]}"
            )

    # ========================================================
    # 저장
    # ========================================================

    write_jsonl(
        OUTPUT_METADATA,
        records,
    )

    write_jsonl(
        OUTPUT_REVIEW,
        review_records,
    )

    # ========================================================
    # 결과
    # ========================================================

    print()
    print("=" * 70)
    print("TXT 추출 완료")
    print("=" * 70)

    print(
        f"전체 원본 PDF        : {len(pdf_files)}"
    )

    print(
        f"고유 PDF 처리        : {paper_number}"
    )

    print(
        f"완전중복 제외        : {duplicate_count}"
    )

    print(
        f"TXT 추출 성공        : {success_count}"
    )

    print(
        f"TXT 추출 실패        : {failed_count}"
    )

    print()
    print(
        f"TXT 폴더:\n"
        f"{TEXT_DIR}"
    )

    print()
    print(
        f"메타데이터:\n"
        f"{OUTPUT_METADATA}"
    )

    print()
    print(
        f"추출 실패 검토:\n"
        f"{OUTPUT_REVIEW}"
    )

    print()
    print(
        "※ 아직 제목/저자/연도는 확정하지 않았습니다."
    )

    print(
        "※ 다음 단계에서 기존 KCI metadata + "
        "PDF 본문을 이용해 확정합니다."
    )


if __name__ == "__main__":
    main()