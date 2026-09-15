from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

INPUT_FILE = METADATA_DIR / "papers_verified.jsonl"

OUTPUT_FILE = (
    METADATA_DIR
    / "document_duplicate_candidates.jsonl"
)

SUMMARY_FILE = (
    METADATA_DIR
    / "document_duplicate_summary.json"
)


def load_jsonl(path: Path):
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


def write_jsonl(path: Path, rows):
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


# ============================================================
# 정규화
# ============================================================

def normalize_title(title):
    if not title:
        return ""

    title = unicodedata.normalize(
        "NFKC",
        str(title),
    )

    title = title.lower()

    # 공백/기호를 제거해서
    # 띄어쓰기 차이를 무시
    title = re.sub(
        r"[^0-9a-z가-힣]",
        "",
        title,
    )

    return title


def normalize_doi(doi):
    if not doi:
        return ""

    doi = str(doi).strip().lower()

    doi = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        doi,
    )

    doi = re.sub(
        r"^doi\s*:\s*",
        "",
        doi,
    )

    doi = doi.rstrip(
        ".,;)"
    )

    return doi


def normalize_authors(authors):
    if not authors:
        return set()

    if not isinstance(
        authors,
        list,
    ):
        authors = [authors]

    result = set()

    for author in authors:

        author = unicodedata.normalize(
            "NFKC",
            str(author),
        ).lower()

        author = re.sub(
            r"[^0-9a-z가-힣]",
            "",
            author,
        )

        if author:
            result.add(author)

    return result


def title_similarity(a, b):
    a = normalize_title(a)
    b = normalize_title(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def author_overlap(a, b):
    a = normalize_authors(a)
    b = normalize_authors(b)

    if not a or not b:
        return False

    return bool(
        a.intersection(b)
    )


# ============================================================
# 후보 등록
# ============================================================

def make_pair_key(a, b):
    return tuple(
        sorted(
            [
                a["paper_id"],
                b["paper_id"],
            ]
        )
    )


def add_candidate(
    candidates,
    seen,
    a,
    b,
    reason,
    score,
):

    pair_key = make_pair_key(
        a,
        b,
    )

    if pair_key in seen:
        return

    seen.add(pair_key)

    candidates.append(
        {
            "paper_id_1": a["paper_id"],
            "paper_id_2": b["paper_id"],

            "title_1": a.get("title"),
            "title_2": b.get("title"),

            "authors_1": a.get("authors"),
            "authors_2": b.get("authors"),

            "year_1": a.get("year"),
            "year_2": b.get("year"),

            "doi_1": a.get("doi"),
            "doi_2": b.get("doi"),

            "source_filename_1": (
                a.get("source_filename")
            ),

            "source_filename_2": (
                b.get("source_filename")
            ),

            "reason": reason,
            "similarity": round(
                score,
                4,
            ),

            # 아직 자동 삭제하지 않음
            "decision": (
                "DUPLICATE_CANDIDATE"
            ),
        }
    )


# ============================================================
# main
# ============================================================

def main():

    papers = load_jsonl(
        INPUT_FILE
    )

    print("=" * 72)
    print("논문 단위 중복 검사")
    print("=" * 72)

    print(
        f"입력 논문            : {len(papers)}"
    )

    candidates = []
    seen = set()

    # --------------------------------------------------------
    # 1. DOI 정확히 동일
    # --------------------------------------------------------

    doi_groups = defaultdict(list)

    for paper in papers:

        doi = normalize_doi(
            paper.get("doi")
        )

        if doi:
            doi_groups[
                doi
            ].append(paper)

    doi_pairs = 0

    for doi, group in (
        doi_groups.items()
    ):

        if len(group) < 2:
            continue

        for i in range(
            len(group)
        ):
            for j in range(
                i + 1,
                len(group),
            ):

                a = group[i]
                b = group[j]

                add_candidate(
                    candidates,
                    seen,
                    a,
                    b,
                    "EXACT_DOI",
                    1.0,
                )

                doi_pairs += 1

    # --------------------------------------------------------
    # 2. 정규화 제목 완전 동일
    # --------------------------------------------------------

    title_groups = defaultdict(list)

    for paper in papers:

        title = normalize_title(
            paper.get("title")
        )

        # 너무 짧은 제목은 제외
        if len(title) >= 10:
            title_groups[
                title
            ].append(paper)

    exact_title_pairs = 0

    for title, group in (
        title_groups.items()
    ):

        if len(group) < 2:
            continue

        for i in range(
            len(group)
        ):
            for j in range(
                i + 1,
                len(group),
            ):

                a = group[i]
                b = group[j]

                pair_key = make_pair_key(
                    a,
                    b,
                )

                if pair_key not in seen:

                    add_candidate(
                        candidates,
                        seen,
                        a,
                        b,
                        "EXACT_NORMALIZED_TITLE",
                        1.0,
                    )

                    exact_title_pairs += 1

    # --------------------------------------------------------
    # 3. 유사 제목 + 저자/연도 보조
    # --------------------------------------------------------

    fuzzy_pairs = 0

    for i in range(
        len(papers)
    ):

        a = papers[i]

        title_a = a.get(
            "title"
        )

        if not title_a:
            continue

        for j in range(
            i + 1,
            len(papers),
        ):

            b = papers[j]

            pair_key = make_pair_key(
                a,
                b,
            )

            if pair_key in seen:
                continue

            title_b = b.get(
                "title"
            )

            if not title_b:
                continue

            score = title_similarity(
                title_a,
                title_b,
            )

            # 92% 미만은 후보로도 잡지 않음
            if score < 0.92:
                continue

            same_year = (
                a.get("year")
                and b.get("year")
                and a.get("year")
                == b.get("year")
            )

            same_author = (
                author_overlap(
                    a.get("authors"),
                    b.get("authors"),
                )
            )

            # 제목만 비슷한 논문은
            # 자동 중복 후보로 만들지 않음.
            if not (
                same_year
                or same_author
            ):
                continue

            reasons = []

            if same_author:
                reasons.append(
                    "AUTHOR_MATCH"
                )

            if same_year:
                reasons.append(
                    "YEAR_MATCH"
                )

            reason = (
                "FUZZY_TITLE_"
                + "_".join(reasons)
            )

            add_candidate(
                candidates,
                seen,
                a,
                b,
                reason,
                score,
            )

            fuzzy_pairs += 1

    # --------------------------------------------------------
    # 결과 정렬
    # --------------------------------------------------------

    priority = {
        "EXACT_DOI": 0,
        "EXACT_NORMALIZED_TITLE": 1,
    }

    candidates.sort(
        key=lambda x: (
            priority.get(
                x["reason"],
                2,
            ),
            -x["similarity"],
            x["paper_id_1"],
            x["paper_id_2"],
        )
    )

    # --------------------------------------------------------
    # 후보에 포함된 paper_id
    # --------------------------------------------------------

    candidate_ids = set()

    for row in candidates:
        candidate_ids.add(
            row["paper_id_1"]
        )

        candidate_ids.add(
            row["paper_id_2"]
        )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_FILE,
        candidates,
    )

    summary = {
        "input_papers": len(papers),
        "candidate_pairs": len(candidates),
        "candidate_papers": len(candidate_ids),

        "exact_doi_pairs": sum(
            1
            for x in candidates
            if x["reason"]
            == "EXACT_DOI"
        ),

        "exact_title_pairs": sum(
            1
            for x in candidates
            if x["reason"]
            == "EXACT_NORMALIZED_TITLE"
        ),

        "fuzzy_pairs": sum(
            1
            for x in candidates
            if x["reason"].startswith(
                "FUZZY_TITLE"
            )
        ),
    }

    with SUMMARY_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # 출력
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("중복 후보 검사 완료")
    print("=" * 72)

    print(
        f"후보 pair            : "
        f"{len(candidates)}"
    )

    print(
        f"후보에 포함된 문서   : "
        f"{len(candidate_ids)}"
    )

    print()

    print(
        f"DOI 동일             : "
        f"{summary['exact_doi_pairs']}"
    )

    print(
        f"정규화 제목 동일     : "
        f"{summary['exact_title_pairs']}"
    )

    print(
        f"유사 제목 후보       : "
        f"{summary['fuzzy_pairs']}"
    )

    print()

    if candidates:

        print("[중복 후보]")

        for row in candidates:

            print()
            print(
                f"{row['paper_id_1']} "
                f"<-> "
                f"{row['paper_id_2']}"
            )

            print(
                f"이유 : {row['reason']}"
            )

            print(
                f"유사도 : "
                f"{row['similarity']}"
            )

            print(
                f"1 : {row['title_1']}"
            )

            print(
                f"2 : {row['title_2']}"
            )

    print()
    print("후보 파일:")
    print(OUTPUT_FILE)

    print()
    print("요약:")
    print(SUMMARY_FILE)

    print()
    print(
        "※ 아직 어떤 PDF/TXT도 "
        "삭제하지 않았습니다."
    )


if __name__ == "__main__":
    main()