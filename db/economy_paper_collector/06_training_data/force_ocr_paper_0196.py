from pathlib import Path
import importlib.util
import tempfile
import json

import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OCR_SCRIPT = (
    PROJECT_ROOT
    / "05_preprocess"
    / "recover_low_text_ocr.py"
)

PAPER_ID = "paper_0196"

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "pdf"
    / "중소기업_스마트공장_보급확산.pdf"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "text_ocr_recovered"
)

OUTPUT_TXT = OUTPUT_DIR / f"{PAPER_ID}_force_ocr.txt"
OUTPUT_META = OUTPUT_DIR / f"{PAPER_ID}_force_ocr_result.json"


def load_ocr_module():
    spec = importlib.util.spec_from_file_location(
        "recover_low_text_ocr",
        OCR_SCRIPT,
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def main():
    print("=" * 72)
    print("paper_0196 전체 페이지 강제 OCR")
    print("=" * 72)

    if not OCR_SCRIPT.exists():
        raise FileNotFoundError(OCR_SCRIPT)

    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    module = load_ocr_module()

    doc = pymupdf.open(PDF_PATH)

    output_parts = []
    page_results = []

    original_total = 0
    ocr_total = 0
    failed_pages = 0

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

            original_total += len(direct_text)

            image_path = (
                temp_dir
                / f"{PAPER_ID}_page_{page_number}.png"
            )

            try:
                module.render_page(
                    page,
                    image_path,
                )

                ocr_text = module.run_tesseract(
                    image_path
                ).strip()

                ocr_total += len(ocr_text)

                output_parts.append(
                    f"\n\n===== PAGE {page_number} =====\n\n"
                    f"{ocr_text}"
                )

                page_results.append(
                    {
                        "page": page_number,
                        "direct_chars": len(direct_text),
                        "ocr_chars": len(ocr_text),
                        "status": "OCR_SUCCESS",
                    }
                )

                print(
                    f"page {page_number:>3}/{len(doc)}"
                    f" | FORCE_OCR"
                    f" | {len(direct_text):>5}"
                    f" -> {len(ocr_text):>5}"
                )

            except Exception as exc:
                failed_pages += 1

                page_results.append(
                    {
                        "page": page_number,
                        "direct_chars": len(direct_text),
                        "ocr_chars": 0,
                        "status": "OCR_FAILED",
                        "error": str(exc),
                    }
                )

                print(
                    f"page {page_number:>3}/{len(doc)}"
                    f" | OCR_FAILED"
                    f" | {exc}"
                )

    doc.close()

    full_text = "".join(
        output_parts
    ).strip()

    OUTPUT_TXT.write_text(
        full_text,
        encoding="utf-8",
    )

    result = {
        "paper_id": PAPER_ID,
        "source_pdf": str(PDF_PATH),
        "page_count": len(page_results),
        "direct_chars": original_total,
        "ocr_chars": ocr_total,
        "failed_pages": failed_pages,
        "pages": page_results,
    }

    OUTPUT_META.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("강제 OCR 완료")
    print("=" * 72)

    print(
        f"기존 직접추출 : {original_total:,}자"
    )

    print(
        f"OCR 추출      : {ocr_total:,}자"
    )

    print(
        f"실패 페이지   : {failed_pages}"
    )

    if original_total:
        print(
            f"글자 수 증가  : "
            f"{ocr_total / original_total:.2f}배"
        )

    print()
    print("결과 TXT:")
    print(OUTPUT_TXT)

    print()
    print("상세 결과:")
    print(OUTPUT_META)

    print()
    print(
        "※ 기존 TXT와 cleaned JSON은 "
        "아직 수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()