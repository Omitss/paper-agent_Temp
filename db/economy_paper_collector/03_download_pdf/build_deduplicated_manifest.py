import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_verified.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_deduplicated.jsonl"
)

DUPLICATE_MAP_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "paper_duplicate_map.jsonl"
)


# duplicate_id : canonical_id
DUPLICATE_MAP = {
    "paper_0064": "paper_0044",
    "paper_0133": "paper_0050",
    "paper_0209": "paper_0108",
    "paper_0183": "paper_0126",
    "paper_0195": "paper_0138",
}


def load_jsonl(path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

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


def main():

    rows = load_jsonl(INPUT_FILE)

    by_id = {
        row["paper_id"]: row
        for row in rows
    }

    # ---------------------------------------------------------
    # 1. 매핑 검증
    # ---------------------------------------------------------

    for duplicate_id, canonical_id in DUPLICATE_MAP.items():

        if duplicate_id not in by_id:
            raise ValueError(
                f"중복 문서 ID 없음: {duplicate_id}"
            )

        if canonical_id not in by_id:
            raise ValueError(
                f"대표 문서 ID 없음: {canonical_id}"
            )

    # ---------------------------------------------------------
    # 2. 중복 매핑 기록 생성
    # ---------------------------------------------------------

    duplicate_records = []

    for duplicate_id, canonical_id in DUPLICATE_MAP.items():

        duplicate = by_id[duplicate_id]
        canonical = by_id[canonical_id]

        duplicate_records.append(
            {
                "duplicate_paper_id": duplicate_id,
                "canonical_paper_id": canonical_id,

                "duplicate_title": duplicate.get("title"),
                "canonical_title": canonical.get("title"),

                "duplicate_source_filename":
                    duplicate.get("source_filename"),

                "canonical_source_filename":
                    canonical.get("source_filename"),

                "reason": "CONFIRMED_DOCUMENT_DUPLICATE",
            }
        )

    # ---------------------------------------------------------
    # 3. 최종 고유 논문 목록 생성
    # ---------------------------------------------------------

    deduplicated_rows = []

    for row in rows:

        paper_id = row["paper_id"]

        if paper_id in DUPLICATE_MAP:
            continue

        new_row = dict(row)

        new_row["is_canonical"] = True
        new_row["duplicate_of"] = None

        deduplicated_rows.append(
            new_row
        )

    # ---------------------------------------------------------
    # 4. 저장
    # ---------------------------------------------------------

    write_jsonl(
        OUTPUT_FILE,
        deduplicated_rows,
    )

    write_jsonl(
        DUPLICATE_MAP_FILE,
        duplicate_records,
    )

    # ---------------------------------------------------------
    # 5. 검증
    # ---------------------------------------------------------

    expected = (
        len(rows)
        - len(DUPLICATE_MAP)
    )

    if len(deduplicated_rows) != expected:
        raise RuntimeError(
            "중복 제거 결과 수가 예상과 다릅니다."
        )

    print("=" * 72)
    print("논문 단위 중복 정리 완료")
    print("=" * 72)

    print(
        f"입력 문서             : {len(rows)}"
    )

    print(
        f"확정 중복 제외        : {len(DUPLICATE_MAP)}"
    )

    print(
        f"최종 고유 문서        : {len(deduplicated_rows)}"
    )

    print()
    print("[중복 매핑]")

    for record in duplicate_records:
        print(
            f"{record['duplicate_paper_id']}"
            f" -> "
            f"{record['canonical_paper_id']}"
        )

    print()
    print("최종 처리 대상:")
    print(OUTPUT_FILE)

    print()
    print("중복 기록:")
    print(DUPLICATE_MAP_FILE)

    print()
    print(
        "※ 원본 PDF/TXT는 삭제하거나 수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()