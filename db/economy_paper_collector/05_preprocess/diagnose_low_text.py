import json
from pathlib import Path

import fitz


PROJECT_ROOT = Path(__file__).resolve().parent.parent

METADATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "papers_preprocessed.jsonl"
)

PDF_DIR = PROJECT_ROOT / "data" / "pdf"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "low_text_diagnosis.jsonl"
)


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


def find_pdf(row):
    """
    metadata 안의 여러 파일명 필드를 우선 확인하고,
    없으면 paper_id 관련 정보로 최대한 탐색한다.
    """

    candidates = [
        row.get("source_filename"),
        row.get("pdf_filename"),
        row.get("filename"),
    ]

    for value in candidates:
        if not value:
            continue

        path = PDF_DIR / Path(value).name

        if path.exists():
            return path

    # pdf_path가 절대/상대 경로로 들어있는 경우
    pdf_path = row.get("pdf_path")

    if pdf_path:
        path = Path(pdf_path)

        if path.exists():
            return path

        path = PDF_DIR / path.name

        if path.exists():
            return path

    return None


def analyze_pdf(pdf_path):
    result = {
        "page_count": 0,
        "normal_text_chars": 0,
        "block_text_chars": 0,
        "dict_text_chars": 0,
        "pages_with_normal_text": 0,
        "pages_with_images": 0,
        "image_count": 0,
        "page_samples": [],
    }

    doc = fitz.open(pdf_path)

    result["page_count"] = len(doc)

    for page_index, page in enumerate(doc):

        # ----------------------------------------------------
        # 방식 1: 일반 text 추출
        # ----------------------------------------------------

        normal_text = page.get_text(
            "text",
            sort=True,
        )

        normal_chars = len(
            normal_text.strip()
        )

        result[
            "normal_text_chars"
        ] += normal_chars

        if normal_chars > 0:
            result[
                "pages_with_normal_text"
            ] += 1

        # ----------------------------------------------------
        # 방식 2: block 추출
        # ----------------------------------------------------

        blocks = page.get_text(
            "blocks",
            sort=True,
        )

        block_text = []

        for block in blocks:

            if len(block) >= 5:
                value = block[4]

                if isinstance(value, str):
                    block_text.append(value)

        block_chars = len(
            "\n".join(block_text).strip()
        )

        result[
            "block_text_chars"
        ] += block_chars

        # ----------------------------------------------------
        # 방식 3: dict/span 추출
        # ----------------------------------------------------

        page_dict = page.get_text(
            "dict"
        )

        spans = []

        for block in page_dict.get(
            "blocks",
            []
        ):

            for line in block.get(
                "lines",
                []
            ):

                for span in line.get(
                    "spans",
                    []
                ):

                    text = span.get(
                        "text",
                        ""
                    )

                    if text:
                        spans.append(text)

        dict_chars = len(
            " ".join(spans).strip()
        )

        result[
            "dict_text_chars"
        ] += dict_chars

        # ----------------------------------------------------
        # 이미지 여부
        # ----------------------------------------------------

        images = page.get_images(
            full=True
        )

        if images:

            result[
                "pages_with_images"
            ] += 1

            result[
                "image_count"
            ] += len(images)

        # ----------------------------------------------------
        # 앞부분 페이지 진단 샘플
        # ----------------------------------------------------

        if page_index < 5:

            result[
                "page_samples"
            ].append(
                {
                    "page":
                        page_index + 1,

                    "normal_chars":
                        normal_chars,

                    "block_chars":
                        block_chars,

                    "dict_chars":
                        dict_chars,

                    "images":
                        len(images),

                    "preview":
                        normal_text[
                            :300
                        ].replace(
                            "\n",
                            " ",
                        ),
                }
            )

    doc.close()

    # --------------------------------------------------------
    # 자동 판정
    # --------------------------------------------------------

    normal = result[
        "normal_text_chars"
    ]

    blocks = result[
        "block_text_chars"
    ]

    dictionary = result[
        "dict_text_chars"
    ]

    pages = result[
        "page_count"
    ]

    image_pages = result[
        "pages_with_images"
    ]

    best_chars = max(
        normal,
        blocks,
        dictionary,
    )

    if best_chars >= 3000:

        diagnosis = (
            "RECOVERABLE_WITH_PYMUPDF"
        )

    elif best_chars >= 500:

        diagnosis = (
            "PARTIAL_TEXT_AVAILABLE"
        )

    elif (
        pages > 0
        and image_pages
        >= max(1, int(pages * 0.5))
    ):

        diagnosis = (
            "LIKELY_SCANNED_PDF"
        )

    elif best_chars == 0:

        diagnosis = (
            "NO_TEXT_LAYER"
        )

    else:

        diagnosis = (
            "VERY_LOW_TEXT"
        )

    result[
        "best_extracted_chars"
    ] = best_chars

    result[
        "diagnosis"
    ] = diagnosis

    return result


def main():

    rows = load_jsonl(
        METADATA_FILE
    )

    low_text_rows = [
        row
        for row in rows
        if row.get(
            "preprocess_status"
        ) == "LOW_TEXT"
    ]

    print("=" * 72)
    print("LOW_TEXT PDF 진단")
    print("=" * 72)
    print(
        f"진단 대상 : {len(low_text_rows)}"
    )
    print()

    results = []

    for index, row in enumerate(
        low_text_rows,
        start=1,
    ):

        paper_id = row[
            "paper_id"
        ]

        pdf_path = find_pdf(row)

        if pdf_path is None:

            result = {
                "paper_id":
                    paper_id,

                "title":
                    row.get("title"),

                "diagnosis":
                    "PDF_NOT_FOUND",
            }

            results.append(result)

            print(
                f"[{index}/{len(low_text_rows)}] "
                f"{paper_id} | PDF_NOT_FOUND"
            )

            continue

        try:

            analysis = analyze_pdf(
                pdf_path
            )

            result = {
                "paper_id":
                    paper_id,

                "title":
                    row.get("title"),

                "pdf_path":
                    str(pdf_path),

                **analysis,
            }

        except Exception as e:

            result = {
                "paper_id":
                    paper_id,

                "title":
                    row.get("title"),

                "pdf_path":
                    str(pdf_path),

                "diagnosis":
                    "PDF_ANALYSIS_ERROR",

                "error":
                    str(e),
            }

        results.append(result)

        print()
        print(
            f"[{index}/{len(low_text_rows)}] "
            f"{paper_id}"
        )

        print(
            "제목:",
            row.get("title")
        )

        print(
            "판정:",
            result.get(
                "diagnosis"
            )
        )

        print(
            "페이지:",
            result.get(
                "page_count"
            )
        )

        print(
            "일반 text:",
            result.get(
                "normal_text_chars"
            )
        )

        print(
            "blocks:",
            result.get(
                "block_text_chars"
            )
        )

        print(
            "dict:",
            result.get(
                "dict_text_chars"
            )
        )

        print(
            "이미지 페이지:",
            result.get(
                "pages_with_images"
            )
        )

    write_jsonl(
        OUTPUT_FILE,
        results,
    )

    print()
    print("=" * 72)
    print("LOW_TEXT 진단 완료")
    print("=" * 72)

    diagnosis_counts = {}

    for row in results:

        status = row.get(
            "diagnosis",
            "UNKNOWN",
        )

        diagnosis_counts[
            status
        ] = (
            diagnosis_counts.get(
                status,
                0,
            )
            + 1
        )

    for status, count in sorted(
        diagnosis_counts.items()
    ):

        print(
            f"{status:<30}: {count}"
        )

    print()
    print("저장:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()