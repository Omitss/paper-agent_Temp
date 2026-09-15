from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF


# ============================================================
# 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PDF_DIR = PROJECT_ROOT / "data" / "pdf"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

OUTPUT_FILE = METADATA_DIR / "pdf_inspection.json"


# ============================================================
# SHA-256
# ============================================================

def calculate_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# PDF 하나 검사
# ============================================================

def inspect_pdf(path: Path) -> dict:
    result = {
        "filename": path.name,
        "source_path": str(path),
        "file_size": path.stat().st_size,

        "sha256": None,

        "valid_pdf": False,
        "encrypted": False,

        "page_count": 0,
        "text_char_count": 0,
        "first_page_preview": "",

        "pdf_title": None,
        "pdf_author": None,
        "pdf_subject": None,

        "status": "UNKNOWN",
        "error": None,
    }

    # --------------------------------------------------------
    # 파일 Hash
    # --------------------------------------------------------

    try:
        result["sha256"] = calculate_sha256(path)

    except Exception as e:
        result["status"] = "HASH_ERROR"
        result["error"] = str(e)
        return result

    # --------------------------------------------------------
    # PDF 열기
    # --------------------------------------------------------

    try:
        document = fitz.open(path)

    except Exception as e:
        result["status"] = "OPEN_ERROR"
        result["error"] = str(e)
        return result

    try:
        result["valid_pdf"] = True
        result["encrypted"] = document.needs_pass
        result["page_count"] = document.page_count

        # ----------------------------------------------------
        # 암호화 PDF
        # ----------------------------------------------------

        if document.needs_pass:
            result["status"] = "ENCRYPTED"
            return result

        # ----------------------------------------------------
        # PDF Metadata
        # ----------------------------------------------------

        metadata = document.metadata or {}

        result["pdf_title"] = (
            metadata.get("title") or None
        )

        result["pdf_author"] = (
            metadata.get("author") or None
        )

        result["pdf_subject"] = (
            metadata.get("subject") or None
        )

        # ----------------------------------------------------
        # 전체 텍스트 추출 가능 여부 검사
        # ----------------------------------------------------

        total_char_count = 0
        preview_parts = []

        for page_index in range(document.page_count):
            try:
                page = document.load_page(page_index)

                text = page.get_text("text") or ""

                total_char_count += len(text.strip())

                # 처음 2페이지 정도만 미리보기 확보
                if page_index < 2 and text.strip():
                    preview_parts.append(text.strip())

            except Exception:
                # 한 페이지 오류 때문에 전체 논문을 실패시키지는 않음
                continue

        result["text_char_count"] = total_char_count

        preview = "\n".join(preview_parts)

        # 너무 길게 저장하지 않음
        result["first_page_preview"] = preview[:4000]

        # ----------------------------------------------------
        # 상태 판단
        # ----------------------------------------------------

        if document.page_count == 0:
            result["status"] = "EMPTY_PDF"

        elif total_char_count == 0:
            # 스캔 이미지 PDF일 가능성
            result["status"] = "NO_TEXT"

        elif total_char_count < 500:
            result["status"] = "VERY_LOW_TEXT"

        else:
            result["status"] = "OK"

        return result

    except Exception as e:
        result["status"] = "INSPECTION_ERROR"
        result["error"] = str(e)

        return result

    finally:
        document.close()


# ============================================================
# 중복 분석
# ============================================================

def analyze_duplicates(records: list[dict]) -> dict[str, list[str]]:
    hash_groups = defaultdict(list)

    for record in records:
        sha256 = record.get("sha256")

        if sha256:
            hash_groups[sha256].append(
                record["filename"]
            )

    duplicate_groups = {}

    for sha256, filenames in hash_groups.items():
        if len(filenames) > 1:
            duplicate_groups[sha256] = filenames

    return duplicate_groups


# ============================================================
# 실행
# ============================================================

def main():
    METADATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_files = sorted(
        PDF_DIR.glob("*.pdf")
    )

    print("=" * 80)
    print("PDF 전체 검사")
    print("=" * 80)

    print()
    print(f"PDF 폴더 : {PDF_DIR}")
    print(f"PDF 개수 : {len(pdf_files):,}")
    print()

    if not pdf_files:
        print("[ERROR] PDF 파일이 없습니다.")
        return

    records = []

    for index, pdf_path in enumerate(
        pdf_files,
        start=1,
    ):
        print(
            f"[{index:03d}/{len(pdf_files):03d}] "
            f"{pdf_path.name}"
        )

        record = inspect_pdf(pdf_path)

        records.append(record)

        print(
            f"    status={record['status']} "
            f"pages={record['page_count']} "
            f"text={record['text_char_count']:,}"
        )

    # ========================================================
    # 완전 동일 PDF
    # ========================================================

    duplicate_groups = analyze_duplicates(records)

    duplicate_extra_count = sum(
        len(files) - 1
        for files in duplicate_groups.values()
    )

    # ========================================================
    # 상태 통계
    # ========================================================

    status_counts = defaultdict(int)

    for record in records:
        status_counts[record["status"]] += 1

    unique_hashes = {
        record["sha256"]
        for record in records
        if record.get("sha256")
    }

    # ========================================================
    # JSON 저장
    # ========================================================

    output = {
        "summary": {
            "total_pdf": len(records),
            "unique_binary_pdf": len(unique_hashes),
            "duplicate_group_count": len(
                duplicate_groups
            ),
            "duplicate_extra_count": (
                duplicate_extra_count
            ),
            "status_counts": dict(status_counts),
        },

        "duplicate_groups": duplicate_groups,

        "papers": records,
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

    # ========================================================
    # 결과 출력
    # ========================================================

    print()
    print("=" * 80)
    print("검사 완료")
    print("=" * 80)

    print()
    print(f"전체 PDF             : {len(records):,}")
    print(
        f"서로 다른 파일 Hash  : "
        f"{len(unique_hashes):,}"
    )
    print(
        f"중복 그룹            : "
        f"{len(duplicate_groups):,}"
    )
    print(
        f"중복 여분 파일       : "
        f"{duplicate_extra_count:,}"
    )

    print()
    print("[상태]")

    for status, count in sorted(
        status_counts.items()
    ):
        print(
            f"{status:20s}: "
            f"{count:,}"
        )

    if duplicate_groups:
        print()
        print("[완전 동일 PDF]")

        for number, filenames in enumerate(
            duplicate_groups.values(),
            start=1,
        ):
            print()
            print(f"중복 그룹 {number}")

            for filename in filenames:
                print(f"  - {filename}")

    print()
    print(f"결과 저장:")
    print(OUTPUT_FILE)

    print()
    print(
        "※ 현재 단계에서는 PDF를 삭제하거나 "
        "수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()