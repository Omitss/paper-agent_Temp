import json
import subprocess
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DIAGNOSIS_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "low_text_diagnosis.jsonl"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "text_ocr_recovered"
)

RESULT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "low_text_ocr_results.jsonl"
)

TESSERACT_EXE = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

TESSDATA_DIR = PROJECT_ROOT / "tessdata"

# 페이지에 이 정도 이상의 텍스트가 이미 있으면
# OCR 대신 기존 PDF 텍스트를 사용
MIN_PAGE_TEXT = 150

# OCR 해상도
DPI = 300


def load_jsonl(path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


def run_tesseract(image_path):
    """
    Tesseract를 직접 실행해서
    한국어 + 영어 OCR 수행
    """

    command = [
        str(TESSERACT_EXE),
        str(image_path),
        "stdout",
        "--tessdata-dir",
        str(TESSDATA_DIR),
        "-l",
        "kor+eng",
        "--psm",
        "6",
        "quiet",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
        )

    return result.stdout.strip()


def render_page(page, output_path):
    """
    PDF 페이지를 300 DPI 이미지로 변환
    """

    zoom = DPI / 72

    matrix = pymupdf.Matrix(
        zoom,
        zoom,
    )

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    pix.save(str(output_path))


def recover_pdf(pdf_path, paper_id):
    doc = pymupdf.open(pdf_path)

    output_parts = []

    normal_chars = 0
    recovered_chars = 0

    direct_pages = 0
    ocr_pages = 0
    failed_pages = 0

    page_results = []

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_dir = Path(temp_dir)

        for page_number, page in enumerate(
            doc,
            start=1,
        ):

            direct_text = page.get_text(
                "text",
                sort=True,
            ).strip()

            normal_chars += len(
                direct_text
            )

            # -----------------------------------------
            # 텍스트가 충분한 페이지
            # → 기존 텍스트 사용
            # -----------------------------------------

            if len(direct_text) >= MIN_PAGE_TEXT:

                final_text = direct_text
                method = "DIRECT_TEXT"

                direct_pages += 1

            else:

                # -------------------------------------
                # 텍스트가 거의 없는 페이지
                # → OCR
                # -------------------------------------

                image_path = (
                    temp_dir
                    / f"{paper_id}_page_{page_number}.png"
                )

                try:

                    render_page(
                        page,
                        image_path,
                    )

                    ocr_text = run_tesseract(
                        image_path
                    )

                    # 기존 텍스트보다 OCR 결과가
                    # 실제로 더 많은 경우에만 OCR 채택
                    if len(ocr_text) > len(direct_text):

                        final_text = ocr_text
                        method = "OCR"

                        ocr_pages += 1

                    else:

                        final_text = direct_text
                        method = "DIRECT_TEXT"

                        direct_pages += 1

                except Exception as e:

                    final_text = direct_text
                    method = "OCR_FAILED"

                    failed_pages += 1

                    print(
                        f"  ! page {page_number} OCR 실패: {e}"
                    )

            recovered_chars += len(
                final_text
            )

            output_parts.append(
                f"\n\n===== PAGE {page_number} =====\n\n"
                f"{final_text}"
            )

            page_results.append(
                {
                    "page": page_number,
                    "original_chars":
                        len(direct_text),
                    "final_chars":
                        len(final_text),
                    "method":
                        method,
                }
            )

            print(
                f"  page {page_number:>3}/{len(doc)}"
                f" | {method:<12}"
                f" | {len(direct_text):>5}"
                f" -> {len(final_text):>5}"
            )

    doc.close()

    return {
        "text":
            "".join(output_parts).strip(),

        "normal_chars":
            normal_chars,

        "recovered_chars":
            recovered_chars,

        "direct_pages":
            direct_pages,

        "ocr_pages":
            ocr_pages,

        "failed_pages":
            failed_pages,

        "pages":
            page_results,
    }


def main():

    if not TESSERACT_EXE.exists():
        raise FileNotFoundError(
            f"Tesseract 없음: {TESSERACT_EXE}"
        )

    if not (
        TESSDATA_DIR
        / "kor.traineddata"
    ).exists():
        raise FileNotFoundError(
            "kor.traineddata 없음"
        )

    if not (
        TESSDATA_DIR
        / "eng.traineddata"
    ).exists():
        raise FileNotFoundError(
            "eng.traineddata 없음"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = load_jsonl(
        DIAGNOSIS_FILE
    )

    print("=" * 72)
    print("LOW_TEXT OCR 복구")
    print("=" * 72)
    print(f"대상 문서 : {len(rows)}")
    print(f"OCR DPI   : {DPI}")
    print("언어      : kor+eng")
    print()

    results = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        paper_id = row["paper_id"]

        pdf_path = Path(
            row["pdf_path"]
        )

        print()
        print("=" * 72)
        print(
            f"[{index}/{len(rows)}] {paper_id}"
        )
        print(row.get("title"))
        print("=" * 72)

        try:

            recovered = recover_pdf(
                pdf_path,
                paper_id,
            )

            output_path = (
                OUTPUT_DIR
                / f"{paper_id}.txt"
            )

            output_path.write_text(
                recovered["text"],
                encoding="utf-8",
            )

            original_chars = row.get(
                "normal_text_chars",
                0,
            )

            recovered_chars = recovered[
                "recovered_chars"
            ]

            if recovered_chars >= 3000:
                status = "RECOVERED"

            elif recovered_chars >= 1000:
                status = "PARTIAL_RECOVERY"

            else:
                status = "STILL_LOW_TEXT"

            result = {
                "paper_id":
                    paper_id,

                "title":
                    row.get("title"),

                "pdf_path":
                    str(pdf_path),

                "output_path":
                    str(output_path),

                "original_chars":
                    original_chars,

                "recovered_chars":
                    recovered_chars,

                "gain_chars":
                    recovered_chars
                    - original_chars,

                "direct_pages":
                    recovered["direct_pages"],

                "ocr_pages":
                    recovered["ocr_pages"],

                "failed_pages":
                    recovered["failed_pages"],

                "status":
                    status,

                "pages":
                    recovered["pages"],
            }

        except Exception as e:

            result = {
                "paper_id":
                    paper_id,

                "title":
                    row.get("title"),

                "pdf_path":
                    str(pdf_path),

                "status":
                    "FAILED",

                "error":
                    str(e),
            }

            print("문서 복구 실패:", e)

        results.append(result)

        print()
        print(
            "결과:",
            result.get("status")
        )

        print(
            "기존 글자:",
            result.get(
                "original_chars"
            )
        )

        print(
            "복구 글자:",
            result.get(
                "recovered_chars"
            )
        )

        print(
            "OCR 페이지:",
            result.get(
                "ocr_pages"
            )
        )

    write_jsonl(
        RESULT_FILE,
        results,
    )

    print()
    print("=" * 72)
    print("OCR 복구 완료")
    print("=" * 72)

    status_counts = {}

    for row in results:

        status = row.get(
            "status",
            "UNKNOWN",
        )

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    for status, count in sorted(
        status_counts.items()
    ):

        print(
            f"{status:<25}: {count}"
        )

    print()
    print("복구 TXT:")
    print(OUTPUT_DIR)

    print()
    print("복구 결과:")
    print(RESULT_FILE)

    print()
    print(
        "※ 기존 data/text 파일은 "
        "수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()