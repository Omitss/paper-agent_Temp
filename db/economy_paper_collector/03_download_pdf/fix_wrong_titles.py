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
    / "papers_verified_before_wrong_title_fix.jsonl"
)


TITLE_FIXES = {
    "paper_0049": (
        "AI 수용성이 조직구성원의 디지털 전환 준비도에 미치는 영향: "
        "중소기업을 중심으로"
    ),

    "paper_0193": (
        "중소기업 제조AI 도입의 조직적 저항 요인 분석: "
        "사회기술 시스템 관점으로"
    ),

    "paper_0203": (
        "중소기업의 디지털 역량과 생성형 AI 활용이 기업성과에 "
        "미치는 영향에 관한 연구: CEO의 혁신역량을 조절변수로"
    ),
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

    # 수정 전 백업
    write_jsonl(
        BACKUP_FILE,
        rows,
    )

    changed = 0

    for row in rows:

        paper_id = row.get("paper_id")

        if paper_id not in TITLE_FIXES:
            continue

        old_title = row.get("title")
        new_title = TITLE_FIXES[paper_id]

        row["previous_title"] = old_title
        row["title"] = new_title
        row["title_validation"] = "MANUALLY_CORRECTED_FROM_SOURCE"

        changed += 1

        print()
        print(paper_id)
        print("기존:", old_title)
        print("수정:", new_title)

    write_jsonl(
        INPUT_FILE,
        rows,
    )

    print()
    print("=" * 72)
    print("제목 수정 완료")
    print("=" * 72)
    print(f"전체 문서 : {len(rows)}")
    print(f"수정 문서 : {changed}")


if __name__ == "__main__":
    main()