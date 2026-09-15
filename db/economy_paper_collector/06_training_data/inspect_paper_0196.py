import json
import re
from pathlib import Path
from difflib import SequenceMatcher


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PAPER_ID = "paper_0196"

TXT_FILE = (
    PROJECT_ROOT
    / "data"
    / "text"
    / f"{PAPER_ID}.txt"
)

CLEANED_FILE = (
    PROJECT_ROOT
    / "data"
    / "cleaned"
    / f"{PAPER_ID}.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / f"{PAPER_ID}_content_check.txt"
)


def normalize(text):
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    return text.strip()


def compact(text):
    """
    공백 차이를 무시하고 실제 내용 비교
    """
    return re.sub(r"\s+", " ", text).strip()


def preview(text, limit=500):
    text = compact(text)

    if len(text) <= limit:
        return text

    return text[:limit] + " ..."


def main():

    print("=" * 80)
    print(f"{PAPER_ID} 상세 검사")
    print("=" * 80)

    if not TXT_FILE.exists():
        print(f"[ERROR] TXT 없음: {TXT_FILE}")
        return

    if not CLEANED_FILE.exists():
        print(f"[ERROR] Cleaned JSON 없음: {CLEANED_FILE}")
        return

    # --------------------------------------------------------
    # 파일 읽기
    # --------------------------------------------------------

    raw_text = normalize(
        TXT_FILE.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    )

    with CLEANED_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        cleaned_data = json.load(f)

    full_text = normalize(
        cleaned_data.get("full_text", "")
    )

    sections = cleaned_data.get(
        "sections",
        [],
    )

    # --------------------------------------------------------
    # 기본 정보
    # --------------------------------------------------------

    raw_compact = compact(raw_text)
    clean_compact = compact(full_text)

    print()
    print("[기본 정보]")

    print(
        f"제목             : "
        f"{cleaned_data.get('title')}"
    )

    print(
        f"원본 TXT 길이    : "
        f"{len(raw_compact):,}자"
    )

    print(
        f"Cleaned 길이     : "
        f"{len(clean_compact):,}자"
    )

    if len(raw_compact):

        ratio = (
            len(clean_compact)
            / len(raw_compact)
            * 100
        )

    else:
        ratio = 0

    print(
        f"보존율           : "
        f"{ratio:.2f}%"
    )

    print(
        f"Section 개수     : "
        f"{len(sections)}"
    )

    # --------------------------------------------------------
    # Section 확인
    # --------------------------------------------------------

    print()
    print("[Cleaned Sections]")

    for i, section in enumerate(
        sections,
        start=1,
    ):

        content = compact(
            section.get(
                "content",
                "",
            )
        )

        print(
            f"{i:02d}. "
            f"{section.get('section')} | "
            f"{section.get('title')} | "
            f"{len(content):,}자"
        )

    # --------------------------------------------------------
    # 앞 / 뒤 비교
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("원본 TXT 시작 부분")
    print("=" * 80)
    print(
        preview(
            raw_compact[:3000],
            1500,
        )
    )

    print()
    print("=" * 80)
    print("Cleaned 시작 부분")
    print("=" * 80)
    print(
        preview(
            clean_compact[:3000],
            1500,
        )
    )

    print()
    print("=" * 80)
    print("원본 TXT 마지막 부분")
    print("=" * 80)
    print(
        raw_compact[-1500:]
    )

    print()
    print("=" * 80)
    print("Cleaned 마지막 부분")
    print("=" * 80)
    print(
        clean_compact[-1500:]
    )

    # --------------------------------------------------------
    # SequenceMatcher로 삭제된 큰 영역 탐색
    # --------------------------------------------------------

    matcher = SequenceMatcher(
        None,
        raw_compact,
        clean_compact,
        autojunk=False,
    )

    removed_blocks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag in {
            "delete",
            "replace",
        }:

            removed = raw_compact[
                i1:i2
            ].strip()

            # 작은 차이는 무시
            if len(removed) >= 300:

                removed_blocks.append(
                    {
                        "tag": tag,
                        "raw_start": i1,
                        "raw_end": i2,
                        "removed_chars": len(
                            removed
                        ),
                        "text": removed,
                    }
                )

    removed_blocks.sort(
        key=lambda x: x[
            "removed_chars"
        ],
        reverse=True,
    )

    print()
    print("=" * 80)
    print("원본에서 사라진 큰 영역")
    print("=" * 80)

    if not removed_blocks:

        print(
            "300자 이상의 큰 삭제 영역을 "
            "찾지 못했습니다."
        )

    else:

        for i, block in enumerate(
            removed_blocks[:10],
            start=1,
        ):

            print()
            print(
                f"[삭제 후보 {i}]"
            )

            print(
                f"유형       : "
                f"{block['tag']}"
            )

            print(
                f"원본 위치  : "
                f"{block['raw_start']:,}"
                f" ~ "
                f"{block['raw_end']:,}"
            )

            print(
                f"삭제 길이  : "
                f"{block['removed_chars']:,}자"
            )

            print(
                "내용:"
            )

            print(
                preview(
                    block["text"],
                    1200,
                )
            )

    # --------------------------------------------------------
    # 결과 파일 저장
    # --------------------------------------------------------

    lines = []

    lines.append(
        f"PAPER ID: {PAPER_ID}"
    )

    lines.append(
        f"TITLE: {cleaned_data.get('title')}"
    )

    lines.append(
        f"RAW CHARS: {len(raw_compact)}"
    )

    lines.append(
        f"CLEANED CHARS: {len(clean_compact)}"
    )

    lines.append(
        f"PRESERVATION: {ratio:.2f}%"
    )

    lines.append("")
    lines.append(
        "=" * 80
    )

    lines.append(
        "REMOVED BLOCKS"
    )

    lines.append(
        "=" * 80
    )

    for i, block in enumerate(
        removed_blocks,
        start=1,
    ):

        lines.append("")
        lines.append(
            f"[{i}] "
            f"{block['tag']} / "
            f"{block['removed_chars']} chars"
        )

        lines.append(
            block["text"]
        )

    OUTPUT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("검사 완료")
    print("=" * 80)

    print(
        f"삭제 후보 영역 : "
        f"{len(removed_blocks)}개"
    )

    print()
    print(
        "상세 결과 파일:"
    )

    print(
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()