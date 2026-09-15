import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

SELECTED_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "training_papers_selected.jsonl"
)

EXCLUDED_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "training_papers_excluded.jsonl"
)


# Transformer가 학술 문체를 배우는 데 사용할 문서 유형
ALLOWED_DOCUMENT_TYPES = {
    "journal_article",
    "master_thesis",
    "doctoral_thesis",
}


# 기본적으로 학습에서 제외할 전처리 상태
EXCLUDED_STATUSES = {
    "LOW_TEXT",
    "VERY_SHORT",
}


MIN_CLEANED_CHARS = 3000


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
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def normalize_document_type(value):
    if not value:
        return "UNKNOWN"

    return str(value).strip().lower()


def main():

    papers = load_jsonl(
        INPUT_FILE
    )

    selected = []
    excluded = []

    selected_type_counter = Counter()
    excluded_reason_counter = Counter()

    print("=" * 72)
    print("Transformer 학습 대상 논문 선별")
    print("=" * 72)
    print(f"전체 입력 논문 : {len(papers)}")
    print()

    for row in papers:

        paper_id = row["paper_id"]

        document_type = normalize_document_type(
            row.get("document_type")
        )

        status = row.get(
            "preprocess_status",
            "UNKNOWN",
        )

        cleaned_chars = int(
            row.get("cleaned_chars") or 0
        )

        reasons = []

        # ----------------------------------------------------
        # 1. 문서 유형
        # ----------------------------------------------------

        if document_type not in ALLOWED_DOCUMENT_TYPES:
            reasons.append(
                f"document_type:{document_type}"
            )

        # ----------------------------------------------------
        # 2. 전처리 품질
        # ----------------------------------------------------

        if status in EXCLUDED_STATUSES:
            reasons.append(
                f"preprocess_status:{status}"
            )

        # ----------------------------------------------------
        # 3. 최소 본문 길이
        # ----------------------------------------------------

        if cleaned_chars < MIN_CLEANED_CHARS:
            reasons.append(
                f"cleaned_chars_under_{MIN_CLEANED_CHARS}"
            )

        # ----------------------------------------------------
        # 결과
        # ----------------------------------------------------

        if reasons:

            excluded_row = dict(row)

            excluded_row[
                "training_eligible"
            ] = False

            excluded_row[
                "training_exclusion_reasons"
            ] = reasons

            excluded.append(
                excluded_row
            )

            for reason in reasons:
                excluded_reason_counter[
                    reason
                ] += 1

        else:

            selected_row = dict(row)

            selected_row[
                "training_eligible"
            ] = True

            selected_row[
                "training_exclusion_reasons"
            ] = []

            selected.append(
                selected_row
            )

            selected_type_counter[
                document_type
            ] += 1

    write_jsonl(
        SELECTED_FILE,
        selected,
    )

    write_jsonl(
        EXCLUDED_FILE,
        excluded,
    )

    print("=" * 72)
    print("선별 완료")
    print("=" * 72)

    print(
        f"전체 논문             : {len(papers)}"
    )

    print(
        f"학습 대상             : {len(selected)}"
    )

    print(
        f"학습 제외             : {len(excluded)}"
    )

    print()
    print("[학습 대상 문서 유형]")

    for key, value in sorted(
        selected_type_counter.items()
    ):
        print(
            f"{key:<25}: {value}"
        )

    print()
    print("[제외 사유]")

    for key, value in sorted(
        excluded_reason_counter.items()
    ):
        print(
            f"{key:<40}: {value}"
        )

    print()
    print("학습 대상:")
    print(SELECTED_FILE)

    print()
    print("학습 제외:")
    print(EXCLUDED_FILE)

    print()
    print(
        "※ 원본/정제 데이터는 수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()