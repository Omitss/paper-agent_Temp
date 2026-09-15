import json
import random
import re
from collections import Counter
from pathlib import Path


# ============================================================
# 설정
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SELECTED_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "training_papers_selected.jsonl"
)

TRAINING_DIR = (
    PROJECT_ROOT
    / "data"
    / "training"
)

TRAIN_FILE = (
    TRAINING_DIR
    / "train.jsonl"
)

VALIDATION_FILE = (
    TRAINING_DIR
    / "validation.jsonl"
)

SUMMARY_FILE = (
    TRAINING_DIR
    / "dataset_summary.json"
)

PAPER_SPLIT_FILE = (
    TRAINING_DIR
    / "paper_split.jsonl"
)


# ------------------------------------------------------------
# Split
# ------------------------------------------------------------

VALIDATION_RATIO = 0.15

RANDOM_SEED = 42


# ------------------------------------------------------------
# Sample 길이
#
# 너무 짧은 문단은 학술 문체 학습에 도움이 적으므로 제외.
# 너무 긴 section은 여러 sample로 분리.
# ------------------------------------------------------------

MIN_SAMPLE_CHARS = 500

TARGET_SAMPLE_CHARS = 2500

MAX_SAMPLE_CHARS = 3500


# ------------------------------------------------------------
# 학습에서 사용할 Section
# ------------------------------------------------------------

TRAINABLE_SECTIONS = {
    "introduction",
    "literature_review",
    "methodology",
    "results",
    "discussion",
    "conclusion",
}


# ============================================================
# JSON
# ============================================================

def load_jsonl(path):

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

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


# ============================================================
# 문장 분리
# ============================================================

def split_sentences(text):

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not text:
        return []

    # 한국어/영어 논문 문장 종결 기준
    sentences = re.split(
        r"(?<=[.!?。！？])\s+",
        text,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


# ============================================================
# 긴 Section → 학습 Sample
# ============================================================

def split_long_sentence(sentence):
    """
    PDF 추출/OCR 과정에서 문장부호가 없어
    하나의 문장이 비정상적으로 길어진 경우 강제로 분할한다.
    """

    sentence = sentence.strip()

    if len(sentence) <= MAX_SAMPLE_CHARS:
        return [sentence]

    pieces = []

    start = 0

    while start < len(sentence):

        end = min(
            start + TARGET_SAMPLE_CHARS,
            len(sentence),
        )

        # 마지막 조각
        if end >= len(sentence):

            piece = sentence[start:].strip()

            if piece:
                pieces.append(piece)

            break

        # 가능한 경우 공백 위치에서 자름
        search_start = max(
            start + MIN_SAMPLE_CHARS,
            end - 300,
        )

        search_end = min(
            len(sentence),
            end + 300,
        )

        window = sentence[
            search_start:search_end
        ]

        space_position = window.rfind(" ")

        if space_position != -1:

            cut = (
                search_start
                + space_position
            )

        else:

            cut = end

        if cut <= start:
            cut = end

        piece = sentence[
            start:cut
        ].strip()

        if piece:
            pieces.append(piece)

        start = cut

    return pieces


def make_text_samples(text):

    sentences = split_sentences(
        text
    )

    if not sentences:
        return []

    # --------------------------------------------------------
    # 비정상적으로 긴 단일 문장을 먼저 분해
    # --------------------------------------------------------

    normalized_sentences = []

    for sentence in sentences:

        normalized_sentences.extend(
            split_long_sentence(
                sentence
            )
        )

    samples = []

    buffer = []
    current_chars = 0

    for sentence in normalized_sentences:

        sentence_chars = len(
            sentence
        )

        # ----------------------------------------------------
        # 현재 buffer + 문장이 MAX를 넘는 경우
        # 기존 buffer 먼저 확정
        # ----------------------------------------------------

        if (
            buffer
            and current_chars
            + sentence_chars
            + 1
            > MAX_SAMPLE_CHARS
        ):

            sample_text = " ".join(
                buffer
            ).strip()

            if len(sample_text) >= MIN_SAMPLE_CHARS:
                samples.append(
                    sample_text
                )

            buffer = []
            current_chars = 0

        # ----------------------------------------------------
        # TARGET에 도달한 상태에서 다음 문장을 넣으면
        # 너무 길어지는 경우 sample 확정
        # ----------------------------------------------------

        elif (
            buffer
            and current_chars
            >= TARGET_SAMPLE_CHARS
        ):

            sample_text = " ".join(
                buffer
            ).strip()

            if len(sample_text) >= MIN_SAMPLE_CHARS:
                samples.append(
                    sample_text
                )

            buffer = []
            current_chars = 0

        buffer.append(
            sentence
        )

        current_chars += (
            sentence_chars + 1
        )

    # --------------------------------------------------------
    # 마지막 buffer 처리
    # --------------------------------------------------------

    if buffer:

        sample_text = " ".join(
            buffer
        ).strip()

        if len(sample_text) >= MIN_SAMPLE_CHARS:

            samples.append(
                sample_text
            )

        elif (
            samples
            and sample_text
        ):

            # 앞 sample과 합쳐도 MAX 이하면 합침
            merged = (
                samples[-1]
                + " "
                + sample_text
            ).strip()

            if len(merged) <= MAX_SAMPLE_CHARS:

                samples[-1] = merged

            # MAX를 넘으면 짧더라도 별도 보존하지 않고
            # 앞쪽 내용 손상을 방지
            else:
                pass

    return samples


# ============================================================
# Section 없는 논문 fallback
# ============================================================

def make_fallback_samples(full_text):

    """
    학술문서인데 section detector가 실패한 경우.

    references가 명확하게 잡히지 않았을 수 있으므로
    전체 본문을 무조건 버리지는 않고 길이 기반 sample 생성.
    """

    if not full_text:
        return []

    return make_text_samples(
        full_text
    )


# ============================================================
# 개별 논문 → Samples
# ============================================================

def build_paper_samples(metadata_row):

    paper_id = metadata_row[
        "paper_id"
    ]

    cleaned_file = Path(
        metadata_row["cleaned_file"]
    )

    if not cleaned_file.exists():

        print(
            f"[WARN] cleaned 파일 없음: "
            f"{paper_id}"
        )

        return []

    with cleaned_file.open(
        "r",
        encoding="utf-8",
    ) as f:

        paper = json.load(f)

    title = (
        paper.get("title")
        or metadata_row.get("title")
        or ""
    )

    metadata = paper.get(
        "metadata",
        {},
    )

    sections = paper.get(
        "sections",
        [],
    )

    samples = []

    sample_index = 0

    # --------------------------------------------------------
    # 정상 Section 활용
    # --------------------------------------------------------

    usable_sections = [
        section
        for section in sections
        if (
            section.get("section")
            in TRAINABLE_SECTIONS
            and section.get(
                "content",
                ""
            ).strip()
        )
    ]

    for section in usable_sections:

        section_name = section[
            "section"
        ]

        section_title = (
            section.get("title")
            or section_name
        )

        text_samples = make_text_samples(
            section["content"]
        )

        for text in text_samples:

            sample_index += 1

            samples.append(
                {
                    "sample_id":
                        f"{paper_id}_sample_{sample_index:04d}",

                    "paper_id":
                        paper_id,

                    "title":
                        title,

                    "section":
                        section_name,

                    "section_title":
                        section_title,

                    "text":
                        text,

                    "char_count":
                        len(text),

                    "authors":
                        metadata.get(
                            "authors"
                        ),

                    "year":
                        metadata.get(
                            "year"
                        ),

                    "journal":
                        metadata.get(
                            "journal"
                        ),

                    "document_type":
                        metadata.get(
                            "document_type"
                        ),

                    "source_mode":
                        "SECTION",
                }
            )

    # --------------------------------------------------------
    # Section을 하나도 활용하지 못한 학술문서
    # --------------------------------------------------------

    if not samples:

        full_text = paper.get(
            "full_text",
            "",
        )

        fallback_samples = (
            make_fallback_samples(
                full_text
            )
        )

        for text in fallback_samples:

            sample_index += 1

            samples.append(
                {
                    "sample_id":
                        f"{paper_id}_sample_{sample_index:04d}",

                    "paper_id":
                        paper_id,

                    "title":
                        title,

                    "section":
                        "full_text",

                    "section_title":
                        None,

                    "text":
                        text,

                    "char_count":
                        len(text),

                    "authors":
                        metadata.get(
                            "authors"
                        ),

                    "year":
                        metadata.get(
                            "year"
                        ),

                    "journal":
                        metadata.get(
                            "journal"
                        ),

                    "document_type":
                        metadata.get(
                            "document_type"
                        ),

                    "source_mode":
                        "FALLBACK_FULL_TEXT",
                }
            )

    return samples


# ============================================================
# Main
# ============================================================

def main():

    TRAINING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    papers = load_jsonl(
        SELECTED_FILE
    )

    print("=" * 72)
    print("Transformer Training Dataset 생성")
    print("=" * 72)

    print(
        f"학습 후보 논문 : {len(papers)}"
    )

    print()

    # --------------------------------------------------------
    # 논문 단위 Split
    # --------------------------------------------------------

    paper_ids = [
        row["paper_id"]
        for row in papers
    ]

    rng = random.Random(
        RANDOM_SEED
    )

    rng.shuffle(
        paper_ids
    )

    validation_count = max(
        1,
        round(
            len(paper_ids)
            * VALIDATION_RATIO
        ),
    )

    validation_ids = set(
        paper_ids[
            :validation_count
        ]
    )

    train_ids = set(
        paper_ids[
            validation_count:
        ]
    )

    # --------------------------------------------------------
    # Split 기록
    # --------------------------------------------------------

    split_rows = []

    for paper_id in sorted(
        paper_ids
    ):

        split_rows.append(
            {
                "paper_id":
                    paper_id,

                "split":
                    (
                        "validation"
                        if paper_id
                        in validation_ids
                        else "train"
                    ),
            }
        )

    write_jsonl(
        PAPER_SPLIT_FILE,
        split_rows,
    )

    # --------------------------------------------------------
    # Sample 생성
    # --------------------------------------------------------

    train_samples = []
    validation_samples = []

    no_sample_papers = []

    section_counter = Counter()
    source_counter = Counter()

    paper_sample_counts = {}

    for index, row in enumerate(
        papers,
        start=1,
    ):

        paper_id = row[
            "paper_id"
        ]

        samples = build_paper_samples(
            row
        )

        paper_sample_counts[
            paper_id
        ] = len(samples)

        if not samples:

            no_sample_papers.append(
                paper_id
            )

        if paper_id in validation_ids:

            split = "validation"

            validation_samples.extend(
                samples
            )

        else:

            split = "train"

            train_samples.extend(
                samples
            )

        for sample in samples:

            section_counter[
                sample["section"]
            ] += 1

            source_counter[
                sample["source_mode"]
            ] += 1

        print(
            f"[{index:03d}/{len(papers)}] "
            f"{paper_id} | "
            f"{split:<10} | "
            f"{len(samples):>3} samples"
        )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    write_jsonl(
        TRAIN_FILE,
        train_samples,
    )

    write_jsonl(
        VALIDATION_FILE,
        validation_samples,
    )

    # --------------------------------------------------------
    # 데이터 누수 검사
    # --------------------------------------------------------

    train_papers_from_samples = {
        sample["paper_id"]
        for sample in train_samples
    }

    validation_papers_from_samples = {
        sample["paper_id"]
        for sample
        in validation_samples
    }

    leakage = (
        train_papers_from_samples
        & validation_papers_from_samples
    )

    # --------------------------------------------------------
    # 샘플 길이 검사
    # --------------------------------------------------------

    all_samples = (
        train_samples
        + validation_samples
    )

    empty_samples = [
        sample["sample_id"]
        for sample in all_samples
        if not sample[
            "text"
        ].strip()
    ]

    too_short_samples = [
        sample["sample_id"]
        for sample in all_samples
        if sample[
            "char_count"
        ] < MIN_SAMPLE_CHARS
    ]

    lengths = [
        sample["char_count"]
        for sample in all_samples
    ]

    if lengths:

        avg_length = (
            sum(lengths)
            / len(lengths)
        )

        min_length = min(
            lengths
        )

        max_length = max(
            lengths
        )

    else:

        avg_length = 0
        min_length = 0
        max_length = 0

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = {
        "source_papers":
            len(papers),

        "train_papers":
            len(train_ids),

        "validation_papers":
            len(validation_ids),

        "train_samples":
            len(train_samples),

        "validation_samples":
            len(validation_samples),

        "total_samples":
            len(all_samples),

        "validation_ratio":
            VALIDATION_RATIO,

        "random_seed":
            RANDOM_SEED,

        "min_sample_chars":
            MIN_SAMPLE_CHARS,

        "target_sample_chars":
            TARGET_SAMPLE_CHARS,

        "max_sample_chars":
            MAX_SAMPLE_CHARS,

        "average_sample_chars":
            round(
                avg_length,
                2,
            ),

        "actual_min_chars":
            min_length,

        "actual_max_chars":
            max_length,

        "paper_leakage_count":
            len(leakage),

        "paper_leakage":
            sorted(leakage),

        "empty_sample_count":
            len(empty_samples),

        "too_short_sample_count":
            len(
                too_short_samples
            ),

        "papers_without_samples":
            no_sample_papers,

        "section_counts":
            dict(
                section_counter
            ),

        "source_mode_counts":
            dict(
                source_counter
            ),
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # 출력
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("Training Dataset 생성 완료")
    print("=" * 72)

    print(
        f"전체 후보 논문       : {len(papers)}"
    )

    print(
        f"Train 논문           : {len(train_ids)}"
    )

    print(
        f"Validation 논문      : {len(validation_ids)}"
    )

    print()

    print(
        f"Train samples        : {len(train_samples)}"
    )

    print(
        f"Validation samples   : {len(validation_samples)}"
    )

    print(
        f"전체 samples         : {len(all_samples)}"
    )

    print()

    print(
        f"평균 sample 길이     : {avg_length:,.1f}"
    )

    print(
        f"최소 sample 길이     : {min_length:,}"
    )

    print(
        f"최대 sample 길이     : {max_length:,}"
    )

    print()

    print(
        f"Train/Val 논문 중복  : {len(leakage)}"
    )

    print(
        f"빈 sample            : {len(empty_samples)}"
    )

    print(
        f"너무 짧은 sample     : {len(too_short_samples)}"
    )

    print(
        f"sample 없는 논문     : {len(no_sample_papers)}"
    )

    print()
    print("[Sample 생성 방식]")

    for key, value in sorted(
        source_counter.items()
    ):
        print(
            f"{key:<25}: {value}"
        )

    print()
    print("[Section별 Sample]")

    for key, value in sorted(
        section_counter.items()
    ):
        print(
            f"{key:<25}: {value}"
        )

    print()
    print("생성 파일:")
    print(TRAIN_FILE)
    print(VALIDATION_FILE)
    print(PAPER_SPLIT_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()