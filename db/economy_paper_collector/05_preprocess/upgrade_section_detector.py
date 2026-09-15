from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGET = (
    PROJECT_ROOT
    / "05_preprocess"
    / "preprocess_papers.py"
)

BACKUP = (
    PROJECT_ROOT
    / "05_preprocess"
    / "preprocess_papers_v1.py"
)


def main():

    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    source = TARGET.read_text(
        encoding="utf-8"
    )

    # 최초 1회만 백업
    if not BACKUP.exists():
        BACKUP.write_text(
            source,
            encoding="utf-8",
        )

    start = source.index(
        "SECTION_PATTERNS = ["
    )

    end = source.index(
        "\n\n\n# ============================================================\n# JSONL",
        start,
    )

    new_block = r'''SECTION_KEYWORDS = {
    "abstract": [
        r"국문\s*초록",
        r"초\s*록",
        r"abstract",
    ],

    "introduction": [
        r"서\s*론",
        r"시작하며",
        r"들어가며",
        r"머리말",
        r"논의의\s*배경",
        r"연구의\s*배경",
        r"연구\s*배경",
        r"연구의\s*필요성",
        r"연구\s*필요성",
        r"연구의\s*목적",
        r"연구\s*목적",
        r"introduction",
    ],

    "literature_review": [
        r"이론적\s*배경",
        r"이론적\s*고찰",
        r"문헌\s*연구",
        r"문헌\s*고찰",
        r"선행\s*연구",
        r"관련\s*연구",
        r"선행연구의\s*검토",
        r"literature\s*review",
        r"theoretical\s*background",
    ],

    "methodology": [
        r"연구\s*방법",
        r"연구\s*방법론",
        r"연구\s*설계",
        r"연구\s*모형",
        r"연구모형의\s*제시",
        r"연구\s*모델",
        r"연구\s*가설",
        r"가설\s*설정",
        r"자료\s*수집",
        r"분석\s*방법",
        r"연구\s*대상",
        r"측정\s*도구",
        r"변수의\s*정의",
        r"research\s*method",
        r"methodology",
        r"methods",
    ],

    "results": [
        r"연구\s*결과",
        r"분석\s*결과",
        r"분석결과",
        r"실증\s*분석",
        r"실증\s*결과",
        r"가설\s*검증",
        r"검증\s*결과",
        r"정량적\s*연구",
        r"정성적\s*연구",
        r"results",
        r"empirical\s*analysis",
    ],

    "discussion": [
        r"논\s*의",
        r"고\s*찰",
        r"종합\s*논의",
        r"discussion",
    ],

    "conclusion": [
        r"결\s*론",
        r"결론\s*및\s*제언",
        r"결론\s*및\s*시사점",
        r"결론\s*및\s*정책적\s*시사점",
        r"요약\s*및\s*결론",
        r"결론\s*및\s*향후\s*연구",
        r"결론\s*및\s*향후\s*과제",
        r"정책적\s*시사점",
        r"conclusion",
        r"conclusions",
    ],

    "references": [
        r"참고\s*문헌",
        r"references",
        r"bibliography",
    ],
}


HEADING_PREFIX = re.compile(
    r"""
    ^\s*
    (?:
        제\s*\d+\s*장
        |
        [ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+
        |
        [IVX]{1,8}
        |
        \d{1,2}
    )
    \s*
    [.\-:)]?
    \s*
    """,
    re.I | re.X,
)
'''

    source = (
        source[:start]
        + new_block
        + source[end:]
    )

    detect_start = source.index(
        "def detect_section(line):"
    )

    detect_end = source.index(
        "\n\ndef split_sections",
        detect_start,
    )

    new_detect = r'''def detect_section(line):

    value = re.sub(
        r"\s+",
        " ",
        line.strip(),
    )

    if not value:
        return None

    # 긴 본문 문장을 섹션 제목으로 오인하지 않도록 제한
    if len(value) > 120:
        return None

    # 앞쪽 장/절 번호 제거
    without_prefix = HEADING_PREFIX.sub(
        "",
        value,
    ).strip()

    # 번호가 없는 제목도 허용
    candidates = [
        value,
        without_prefix,
    ]

    for candidate in candidates:

        candidate = candidate.strip(
            " .:-–—"
        )

        for section_name, keywords in SECTION_KEYWORDS.items():

            for keyword in keywords:

                # 참고문헌/초록처럼 제목 전체가 짧고 명확한 경우
                if re.fullmatch(
                    keyword,
                    candidate,
                    re.I,
                ):
                    return section_name

                # 장 제목:
                # "결론 및 정책적 시사점"
                # "문헌연구 및 이론적 배경"
                # "연구모형의 제시"
                #
                # 본문 오탐 방지를 위해 60자 이하만 허용
                if (
                    len(candidate) <= 60
                    and re.search(
                        keyword,
                        candidate,
                        re.I,
                    )
                ):
                    return section_name

    return None
'''

    source = (
        source[:detect_start]
        + new_detect
        + source[detect_end:]
    )

    TARGET.write_text(
        source,
        encoding="utf-8",
    )

    print("=" * 72)
    print("섹션 탐지기 업그레이드 완료")
    print("=" * 72)
    print("수정:", TARGET)
    print("백업:", BACKUP)


if __name__ == "__main__":
    main()