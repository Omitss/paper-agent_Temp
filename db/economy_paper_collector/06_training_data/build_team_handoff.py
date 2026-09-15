import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

HANDOFF_ROOT = PROJECT_ROOT / "team_handoff"

RAG_DIR = HANDOFF_ROOT / "01_rag_input"
TRANSFORMER_DIR = HANDOFF_ROOT / "02_transformer_input"
DOC_DIR = HANDOFF_ROOT / "03_info"


# ============================================================
# 복사 함수
# ============================================================

def copy_file(source: Path, destination: Path):

    if not source.exists():
        print(f"[WARN] 파일 없음: {source}")
        return False

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )

    return True


def copy_directory(source: Path, destination: Path):

    if not source.exists():
        print(f"[WARN] 폴더 없음: {source}")
        return False

    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(
        source,
        destination,
    )

    return True


# ============================================================
# 안내문
# ============================================================

README = """# 경제 논문 데이터 전달본

주제
AI가 중소기업에 미치는 영향

============================================================
1. RAG 담당자
============================================================

사용 폴더:

01_rag_input/
├─ cleaned/
└─ papers_preprocessed.jsonl


cleaned/

전처리가 완료된 논문 JSON입니다.

총 전처리 대상:
211편


각 JSON의 주요 필드:

paper_id
title
metadata
quality
full_text
sections


RAG에서는 full_text를 무작정 고정 길이로 자르기보다
sections 정보를 우선 사용해 section-aware chunking을 권장합니다.

예:

introduction
literature_review
methodology
results
discussion
conclusion


주의:

이 폴더에는 RAG Chunk나 Embedding이 아직 없습니다.

담당자가 다음 작업을 수행해야 합니다.

cleaned JSON
    ↓
Section-aware Chunk
    ↓
BGE-M3 Embedding
    ↓
PostgreSQL / pgvector


기존 경제 뉴스 DB가 존재하므로
새 DB를 만드는 것이 아니라 다음 테이블을 추가하는 구조를 권장합니다.

papers
paper_chunks


============================================================
2. Transformer 담당자
============================================================

사용 폴더:

02_transformer_input/


파일:

train.jsonl
validation.jsonl
paper_split.jsonl
dataset_summary.json
training_papers_selected.jsonl
training_papers_excluded.jsonl


최종 학습 대상 논문:
180편


Train:

153편
3,696 samples


Validation:

27편
810 samples


전체:

4,506 samples


검증 결과:

Train / Validation paper_id 중복 = 0
빈 sample = 0
500자 미만 sample = 0
sample 없는 논문 = 0


Sample 길이:

최소 500자
최대 3,477자
평균 약 1,625.5자


중요:

train.jsonl / validation.jsonl은
RAG Chunk가 아닙니다.

Transformer Fine-tuning용 데이터입니다.


모델 학습 시 사용하는 tokenizer의 max_length에 맞춰
tokenization / truncation 설정은 학습 코드에서 처리해야 합니다.


Transformer A와 Transformer B는 반드시 동일한

train.jsonl
validation.jsonl

을 사용해야 비교가 가능합니다.


============================================================
3. 데이터 흐름
============================================================

원본 PDF
    ↓
PDF 검사
    ↓
Metadata 정리
    ↓
Binary 중복 제거
    ↓
논문 단위 중복 제거
    ↓
최종 211편
    ↓
PDF → TXT
    ↓
OCR 복구
    ↓
전처리 / Section 탐지
    ↓
cleaned JSON
    │
    ├──────── RAG
    │           ↓
    │         Chunk
    │           ↓
    │         BGE-M3
    │           ↓
    │         pgvector
    │
    └──────── Transformer
                ↓
             180편 선별
                ↓
             Train / Validation
                ↓
             Fine-tuning


============================================================
4. 주의
============================================================

RAG 담당자:

02_transformer_input/train.jsonl을 다시 Chunk하지 마세요.
RAG 원본은 01_rag_input/cleaned 입니다.


Transformer 담당자:

01_rag_input/cleaned 전체 211편을 그대로 학습시키지 마세요.
Transformer 학습 대상은 검증 후 선별한 180편입니다.


원본 PDF가 필요한 경우 별도로 요청하세요.
이 전달본에는 용량 절약을 위해 원본 PDF를 포함하지 않았습니다.
"""


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 72)
    print("팀원 전달용 데이터 생성")
    print("=" * 72)

    # 기존 전달본 제거
    if HANDOFF_ROOT.exists():
        shutil.rmtree(HANDOFF_ROOT)

    RAG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    TRANSFORMER_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    DOC_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    print()
    print("[1] RAG 데이터 복사")

    copy_directory(
        PROJECT_ROOT / "data" / "cleaned",
        RAG_DIR / "cleaned",
    )

    copy_file(
        PROJECT_ROOT
        / "data"
        / "metadata"
        / "papers_preprocessed.jsonl",

        RAG_DIR
        / "papers_preprocessed.jsonl",
    )

    # --------------------------------------------------------
    # Transformer
    # --------------------------------------------------------

    print("[2] Transformer 데이터 복사")

    transformer_files = [
        (
            PROJECT_ROOT
            / "data"
            / "training"
            / "train.jsonl"
        ),
        (
            PROJECT_ROOT
            / "data"
            / "training"
            / "validation.jsonl"
        ),
        (
            PROJECT_ROOT
            / "data"
            / "training"
            / "paper_split.jsonl"
        ),
        (
            PROJECT_ROOT
            / "data"
            / "training"
            / "dataset_summary.json"
        ),
        (
            PROJECT_ROOT
            / "data"
            / "metadata"
            / "training_papers_selected.jsonl"
        ),
        (
            PROJECT_ROOT
            / "data"
            / "metadata"
            / "training_papers_excluded.jsonl"
        ),
    ]

    for source in transformer_files:

        copy_file(
            source,
            TRANSFORMER_DIR / source.name,
        )

    # --------------------------------------------------------
    # README
    # --------------------------------------------------------

    print("[3] 안내문 생성")

    readme_path = (
        DOC_DIR
        / "README_DATA_HANDOFF.txt"
    )

    readme_path.write_text(
        README,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # ZIP
    # --------------------------------------------------------

    print("[4] ZIP 생성")

    zip_base = (
        PROJECT_ROOT
        / "economy_paper_data_handoff"
    )

    zip_file = Path(
        str(zip_base) + ".zip"
    )

    if zip_file.exists():
        zip_file.unlink()

    shutil.make_archive(
        str(zip_base),
        "zip",
        root_dir=HANDOFF_ROOT,
    )

    # --------------------------------------------------------
    # 통계
    # --------------------------------------------------------

    cleaned_files = list(
        (
            RAG_DIR
            / "cleaned"
        ).glob("*.json")
    )

    transformer_existing = [
        path
        for path in TRANSFORMER_DIR.iterdir()
        if path.is_file()
    ]

    print()
    print("=" * 72)
    print("전달본 생성 완료")
    print("=" * 72)

    print(
        f"RAG cleaned JSON       : "
        f"{len(cleaned_files)}"
    )

    print(
        f"Transformer 관련 파일 : "
        f"{len(transformer_existing)}"
    )

    print()
    print("전달 폴더:")
    print(HANDOFF_ROOT)

    print()
    print("ZIP:")
    print(zip_file)

    print()
    print(
        "※ 원본 프로젝트 데이터는 수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()