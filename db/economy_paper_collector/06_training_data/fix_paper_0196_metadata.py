from __future__ import annotations

import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "metadata"
CLEANED_DIR = DATA_DIR / "cleaned"

PAPER_ID = "paper_0196"

CORRECT = {
    "title": "중소기업 스마트공장 보급확산에 미치는 요인에 관한 연구 : 전북지역 사례를 중심으로",
    "authors": "이지훈",
    "year": 2021,
    "journal": "혁신클러스터연구",
    "doi": "10.23205/isic.2021.11.2.1",
    "kci_id": "ART002787353",
    "document_type": "journal_article",
}

# paper_0196의 서지정보가 들어갈 수 있는 canonical/downstream metadata
METADATA_FILES = [
    METADATA_DIR / "papers_verified.jsonl",
    METADATA_DIR / "papers_deduplicated.jsonl",
    METADATA_DIR / "papers_preprocessed.jsonl",
]

CLEANED_FILE = CLEANED_DIR / f"{PAPER_ID}.json"

BACKUP_DIR = DATA_DIR / "backup_paper_0196_metadata"
BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def backup_file(path: Path) -> None:
    if not path.exists():
        return

    destination = BACKUP_DIR / path.name

    # 이전 백업을 실수로 덮어쓰지 않는다.
    if not destination.exists():
        shutil.copy2(
            path,
            destination,
        )


def update_jsonl(path: Path) -> bool:
    if not path.exists():
        print(f"[SKIP] 파일 없음: {path}")
        return False

    backup_file(path)

    rows = []
    found = False

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            row = json.loads(line)

            if row.get("paper_id") == PAPER_ID:
                for key, value in CORRECT.items():
                    row[key] = value

                found = True

            rows.append(row)

    if not found:
        print(
            f"[WARNING] {path.name}: "
            f"{PAPER_ID} 없음"
        )
        return False

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

    print(
        f"[OK] {path.name}: "
        f"{PAPER_ID} 수정"
    )

    return True


def update_cleaned_json() -> bool:
    if not CLEANED_FILE.exists():
        print(
            f"[ERROR] cleaned JSON 없음: "
            f"{CLEANED_FILE}"
        )
        return False

    backup_file(CLEANED_FILE)

    data = json.loads(
        CLEANED_FILE.read_text(
            encoding="utf-8"
        )
    )

    # 본문과 sections는 절대 수정하지 않는다.
    original_full_text = data.get(
        "full_text"
    )
    original_sections = data.get(
        "sections"
    )

    data["title"] = CORRECT["title"]

    metadata = data.setdefault(
        "metadata",
        {},
    )

    metadata["authors"] = CORRECT["authors"]
    metadata["year"] = CORRECT["year"]
    metadata["journal"] = CORRECT["journal"]
    metadata["doi"] = CORRECT["doi"]
    metadata["document_type"] = CORRECT["document_type"]
    metadata["kci_id"] = CORRECT["kci_id"]

    # 안전 검증:
    # 본문/섹션이 수정되지 않았는지 확인
    if data.get("full_text") != original_full_text:
        raise RuntimeError(
            "full_text가 변경되었습니다."
        )

    if data.get("sections") != original_sections:
        raise RuntimeError(
            "sections가 변경되었습니다."
        )

    CLEANED_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "[OK] paper_0196.json "
        "서지정보 수정"
    )
    print(
        f"     full_text: "
        f"{len(original_full_text or ''):,}자 유지"
    )
    print(
        f"     sections : "
        f"{len(original_sections or [])}개 유지"
    )

    return True


def verify() -> None:
    print()
    print("=" * 72)
    print("최종 확인")
    print("=" * 72)

    for path in METADATA_FILES:
        if not path.exists():
            continue

        target = None

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                row = json.loads(line)

                if row.get("paper_id") == PAPER_ID:
                    target = row
                    break

        if target is None:
            print(
                f"{path.name}: "
                "paper_0196 없음"
            )
            continue

        print()
        print(path.name)
        print(
            "  title   :",
            target.get("title"),
        )
        print(
            "  authors :",
            target.get("authors"),
        )
        print(
            "  year    :",
            target.get("year"),
        )
        print(
            "  journal :",
            target.get("journal"),
        )
        print(
            "  doi     :",
            target.get("doi"),
        )
        print(
            "  kci_id  :",
            target.get("kci_id"),
        )

    cleaned = json.loads(
        CLEANED_FILE.read_text(
            encoding="utf-8"
        )
    )

    print()
    print("paper_0196.json")
    print(
        "  title       :",
        cleaned.get("title"),
    )
    print(
        "  metadata    :",
        cleaned.get("metadata"),
    )
    print(
        "  full_text   :",
        f"{len(cleaned.get('full_text') or ''):,}자",
    )
    print(
        "  sections    :",
        len(cleaned.get("sections") or []),
    )


def main() -> None:
    print("=" * 72)
    print("paper_0196 서지정보 수정")
    print("=" * 72)

    print()
    print("[1] Metadata JSONL 수정")

    for path in METADATA_FILES:
        update_jsonl(path)

    print()
    print("[2] Cleaned JSON 수정")

    update_cleaned_json()

    print()
    print("[3] 검증")

    verify()

    print()
    print("=" * 72)
    print("수정 완료")
    print("=" * 72)
    print(
        f"백업 위치: {BACKUP_DIR}"
    )
    print(
        "※ full_text와 sections는 수정하지 않았습니다."
    )


if __name__ == "__main__":
    main()