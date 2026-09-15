import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_verified.jsonl"
)

BACKUP_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_verified_before_doi_fix.jsonl"
)


BAD_DOIS = {
    "10.14400/jdc.2015.13.8.301",
    "10.18237/kdgw.2016.34.3.037",
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


def normalize_doi(value):
    if not value:
        return ""

    return str(value).strip().lower()


def main():

    rows = load_jsonl(
        INPUT_FILE
    )

    # 수정 전 백업
    write_jsonl(
        BACKUP_FILE,
        rows,
    )

    changed = 0

    print("=" * 72)
    print("잘못 추출된 DOI 정리")
    print("=" * 72)

    for row in rows:

        doi = normalize_doi(
            row.get("doi")
        )

        if doi not in BAD_DOIS:
            continue

        print(
            f"{row.get('paper_id')} | "
            f"{doi} | "
            f"{row.get('title')}"
        )

        # 잘못된 값이라는 기록은 남겨둠
        row["invalid_doi_removed"] = doi

        row["doi"] = None

        row["doi_validation"] = (
            "REMOVED_NOT_FOUND_IN_FULLTEXT"
        )

        changed += 1

    write_jsonl(
        INPUT_FILE,
        rows,
    )

    print()
    print("=" * 72)
    print("DOI 정리 완료")
    print("=" * 72)

    print(
        f"전체 문서           : {len(rows)}"
    )

    print(
        f"잘못된 DOI 제거     : {changed}"
    )

    print()
    print("수정 파일:")
    print(INPUT_FILE)

    print()
    print("백업 파일:")
    print(BACKUP_FILE)


if __name__ == "__main__":
    main()