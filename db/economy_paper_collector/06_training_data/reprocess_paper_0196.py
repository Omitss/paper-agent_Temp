from pathlib import Path
import importlib.util
import json
import shutil


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PREPROCESS_SCRIPT = (
    PROJECT_ROOT
    / "05_preprocess"
    / "preprocess_papers.py"
)

PAPER_ID = "paper_0196"

METADATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_deduplicated.jsonl"
)

PREPROCESSED_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

CLEANED_FILE = (
    PROJECT_ROOT
    / "data"
    / "cleaned"
    / f"{PAPER_ID}.json"
)

BACKUP_DIR = (
    PROJECT_ROOT
    / "data"
    / "backup_paper_0196"
)


def load_jsonl(path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(
                    json.loads(line)
                )

    return rows


def write_jsonl(path, rows):
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


def load_preprocess_module():
    spec = importlib.util.spec_from_file_location(
        "preprocess_papers",
        PREPROCESS_SCRIPT,
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def main():
    print("=" * 72)
    print("paper_0196 단독 재전처리")
    print("=" * 72)

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------
    # 기존 결과 백업
    # --------------------------------------------------

    if CLEANED_FILE.exists():
        shutil.copy2(
            CLEANED_FILE,
            BACKUP_DIR / CLEANED_FILE.name,
        )

    if PREPROCESSED_FILE.exists():
        shutil.copy2(
            PREPROCESSED_FILE,
            BACKUP_DIR / PREPROCESSED_FILE.name,
        )

    print("기존 결과 백업 완료")

    # --------------------------------------------------
    # paper_0196 원본 metadata 찾기
    # --------------------------------------------------

    metadata_rows = load_jsonl(
        METADATA_FILE
    )

    target_row = next(
        (
            row
            for row in metadata_rows
            if row.get("paper_id") == PAPER_ID
        ),
        None,
    )

    if target_row is None:
        raise RuntimeError(
            f"{PAPER_ID}를 metadata에서 찾지 못했습니다."
        )

    # --------------------------------------------------
    # 기존 전처리 모듈 로드
    # --------------------------------------------------

    module = load_preprocess_module()

    source_path, source_type = (
        module.select_text_source(
            target_row
        )
    )

    print()
    print(f"선택된 입력 : {source_path}")
    print(f"입력 방식   : {source_type}")

    if source_type != "OCR_RECOVERED":
        raise RuntimeError(
            "OCR_RECOVERED 파일이 선택되지 않았습니다."
        )

    # --------------------------------------------------
    # paper_0196 하나만 기존 로직으로 전처리
    # --------------------------------------------------

    result, detail = module.preprocess_paper(
        target_row
    )

    if result is None:
        print()
        print("재전처리 실패")
        print(detail)
        return



    # --------------------------------------------------
    # papers_preprocessed.jsonl에서
    # paper_0196 레코드만 교체
    # --------------------------------------------------

    preprocessed_rows = load_jsonl(
        PREPROCESSED_FILE
    )

    replaced = False

    for index, row in enumerate(
        preprocessed_rows
    ):
        if row.get("paper_id") == PAPER_ID:
            preprocessed_rows[index] = result
            replaced = True
            break

    if not replaced:
        preprocessed_rows.append(
            result
        )

    write_jsonl(
        PREPROCESSED_FILE,
        preprocessed_rows,
    )

    # --------------------------------------------------
    # 결과
    # --------------------------------------------------

    print()
    print("=" * 72)
    print("paper_0196 재전처리 완료")
    print("=" * 72)

    print(
        f"상태          : "
        f"{result.get('preprocess_status')}"
    )

    print(
        f"텍스트 소스   : "
        f"{result.get('text_source')}"
    )

    print(
        f"원본 글자 수  : "
        f"{result.get('raw_chars', 0):,}"
    )

    print(
        f"정제 글자 수  : "
        f"{result.get('cleaned_chars', 0):,}"
    )

    print(
        f"섹션 수       : "
        f"{result.get('section_count', 0)}"
    )

    print(
        f"감지된 섹션   : "
        f"{result.get('detected_sections')}"
    )

    print()
    print(
        f"cleaned JSON  : {CLEANED_FILE}"
    )

    print(
        f"metadata 갱신 : {PREPROCESSED_FILE}"
    )

    print(
        f"백업 위치     : {BACKUP_DIR}"
    )

    print()
    print(
        "※ 다른 논문의 cleaned JSON은 "
        "수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()