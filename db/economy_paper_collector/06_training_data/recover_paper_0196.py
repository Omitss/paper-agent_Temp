from pathlib import Path
import importlib.util
import json


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

OUTPUT_TXT = OUTPUT_DIR / f"{PAPER_ID}.txt"
OUTPUT_META = OUTPUT_DIR / f"{PAPER_ID}_ocr_result.json"


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
    print("paper_0196 단독 OCR 복구")
    print("=" * 72)

    print(f"Paper ID : {PAPER_ID}")
    print(f"PDF      : {PDF_PATH}")
    print()

    if not OCR_SCRIPT.exists():
        raise FileNotFoundError(
            f"OCR 스크립트를 찾을 수 없습니다:\n{OCR_SCRIPT}"
        )

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"PDF를 찾을 수 없습니다:\n{PDF_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    module = load_ocr_module()

    print("기존 OCR 함수를 사용하여 복구를 시작합니다.")
    print()

    result = module.recover_pdf(
        PDF_PATH,
        PAPER_ID,
    )

    recovered_text = result["text"]

    # --------------------------------------------------
    # OCR 결과 저장
    # 기존 data/text/paper_0196.txt는 절대 수정하지 않음
    # --------------------------------------------------

    OUTPUT_TXT.write_text(
        recovered_text,
        encoding="utf-8",
    )

    metadata = {
        "paper_id": PAPER_ID,
        "source_pdf": str(PDF_PATH),
        "output_txt": str(OUTPUT_TXT),

        "normal_chars": result["normal_chars"],
        "recovered_chars": result["recovered_chars"],

        "direct_pages": result["direct_pages"],
        "ocr_pages": result["ocr_pages"],
        "failed_pages": result["failed_pages"],

        "pages": result["pages"],
    }

    OUTPUT_META.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("OCR 복구 완료")
    print("=" * 72)

    print(
        f"기존 PyMuPDF 글자 수 : "
        f"{result['normal_chars']:,}"
    )

    print(
        f"최종 복구 글자 수    : "
        f"{result['recovered_chars']:,}"
    )

    print(
        f"직접 추출 페이지     : "
        f"{result['direct_pages']}"
    )

    print(
        f"OCR 페이지           : "
        f"{result['ocr_pages']}"
    )

    print(
        f"실패 페이지          : "
        f"{result['failed_pages']}"
    )

    print()

    if result["normal_chars"] > 0:
        ratio = (
            result["recovered_chars"]
            / result["normal_chars"]
        )

        print(
            f"복구 전 대비 글자 수 : "
            f"{ratio:.2f}배"
        )

    print()
    print("OCR TXT:")
    print(OUTPUT_TXT)

    print()
    print("OCR 상세 결과:")
    print(OUTPUT_META)

    print()
    print(
        "※ 기존 data/text/paper_0196.txt는 "
        "수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()