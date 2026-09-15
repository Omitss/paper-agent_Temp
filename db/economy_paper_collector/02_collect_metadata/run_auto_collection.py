from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# =========================================================
# 경로
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

COLLECT_SCRIPT = (
    SCRIPT_DIR
    / "collect_kci_oai_all.py"
)

FILTER_SCRIPT = (
    SCRIPT_DIR
    / "filter_sme_papers.py"
)

METADATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "metadata"
)

RESULT_FILE = (
    METADATA_DIR
    / "kci_sme_relevant.json"
)

STATE_FILE = (
    METADATA_DIR
    / "kci_oai_state.json"
)

LOG_FILE = (
    METADATA_DIR
    / "auto_collection.log"
)


# =========================================================
# 설정
# =========================================================

# 관련 후보가 이 숫자 이상이면 자동 종료
TARGET_RELEVANT = 300

# 실패했을 때 다시 시도하기 전 대기시간
RETRY_WAIT_SECONDS = 30

# 한 사이클 종료 후 다음 수집까지 잠깐 대기
NEXT_CYCLE_WAIT_SECONDS = 5

# 무한 오류 방지
MAX_CONSECUTIVE_ERRORS = 10


# =========================================================
# 로그
# =========================================================

def log(message: str) -> None:

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    line = (
        f"[{timestamp}] {message}"
    )

    print(
        line,
        flush=True,
    )

    METADATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            line + "\n"
        )


# =========================================================
# Python script 실행
# =========================================================

def run_script(
    script_path: Path,
) -> bool:

    log(
        f"실행 시작: {script_path.name}"
    )

    try:

        process = subprocess.run(
            [
                sys.executable,
                str(script_path),
            ],
            cwd=str(
                PROJECT_ROOT
            ),
            check=False,
        )

        if process.returncode == 0:

            log(
                f"정상 완료: {script_path.name}"
            )

            return True

        log(
            f"실행 실패: "
            f"{script_path.name} "
            f"returncode="
            f"{process.returncode}"
        )

        return False

    except Exception as exc:

        log(
            f"예외 발생: "
            f"{script_path.name} "
            f"{exc}"
        )

        return False


# =========================================================
# 관련 논문 수 확인
# =========================================================

def get_relevant_count() -> int:

    if not RESULT_FILE.exists():
        return 0

    try:

        with RESULT_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        if isinstance(
            data,
            list,
        ):
            return len(data)

    except Exception as exc:

        log(
            f"결과 파일 읽기 실패: {exc}"
        )

    return 0


# =========================================================
# OAI 전체 수집 완료 여부
# =========================================================

def is_collection_finished() -> bool:

    if not STATE_FILE.exists():
        return False

    try:

        with STATE_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        return bool(
            state.get(
                "finished",
                False,
            )
        )

    except Exception as exc:

        log(
            f"state 읽기 실패: {exc}"
        )

        return False


# =========================================================
# 총 저장 수
# =========================================================

def get_total_saved() -> int:

    if not STATE_FILE.exists():
        return 0

    try:

        with STATE_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        return int(
            state.get(
                "total_saved",
                0,
            )
        )

    except Exception:
        return 0


# =========================================================
# main
# =========================================================

def main():

    print()
    print("=" * 90)
    print("KCI 논문 자동 수집 시스템")
    print("=" * 90)

    log(
        "자동 수집 시작"
    )

    log(
        f"목표 관련 논문 수: "
        f"{TARGET_RELEVANT}"
    )

    log(
        f"사용 Python: "
        f"{sys.executable}"
    )

    consecutive_errors = 0
    cycle = 0

    while True:

        cycle += 1

        print()
        print("=" * 90)

        log(
            f"CYCLE {cycle} 시작"
        )

        print("=" * 90)

        # =================================================
        # 이미 목표 달성했는지 확인
        # =================================================

        current_count = (
            get_relevant_count()
        )

        if (
            current_count
            >= TARGET_RELEVANT
        ):

            log(
                f"목표 달성: "
                f"{current_count}개"
            )

            break

        # =================================================
        # KCI 전체 데이터가 이미 끝까지 수집된 경우
        # =================================================

        if is_collection_finished():

            log(
                "KCI OAI 전체 수집이 "
                "이미 완료된 상태"
            )

            log(
                "마지막 필터링 실행"
            )

            run_script(
                FILTER_SCRIPT
            )

            final_count = (
                get_relevant_count()
            )

            log(
                f"최종 관련 논문: "
                f"{final_count}개"
            )

            break

        # =================================================
        # 1. 메타데이터 수집
        # =================================================

        collect_success = (
            run_script(
                COLLECT_SCRIPT
            )
        )

        if not collect_success:

            consecutive_errors += 1

            log(
                f"연속 오류: "
                f"{consecutive_errors}/"
                f"{MAX_CONSECUTIVE_ERRORS}"
            )

            if (
                consecutive_errors
                >= MAX_CONSECUTIVE_ERRORS
            ):

                log(
                    "오류가 너무 많이 발생하여 "
                    "자동 작업을 종료합니다."
                )

                break

            log(
                f"{RETRY_WAIT_SECONDS}초 후 "
                "다시 시도"
            )

            time.sleep(
                RETRY_WAIT_SECONDS
            )

            continue

        consecutive_errors = 0

        # =================================================
        # 2. 관련 논문 필터링
        # =================================================

        filter_success = (
            run_script(
                FILTER_SCRIPT
            )
        )

        if not filter_success:

            consecutive_errors += 1

            log(
                "필터링 실패"
            )

            time.sleep(
                RETRY_WAIT_SECONDS
            )

            continue

        # =================================================
        # 3. 결과 확인
        # =================================================

        relevant_count = (
            get_relevant_count()
        )

        total_saved = (
            get_total_saved()
        )

        log(
            f"현재 KCI 저장: "
            f"{total_saved:,}개"
        )

        log(
            f"현재 관련 후보: "
            f"{relevant_count:,}개"
        )

        # =================================================
        # 4. 목표 달성
        # =================================================

        if (
            relevant_count
            >= TARGET_RELEVANT
        ):

            log(
                "================================"
            )

            log(
                "관련 논문 목표 달성"
            )

            log(
                f"관련 후보: "
                f"{relevant_count:,}"
            )

            log(
                "================================"
            )

            break

        # =================================================
        # 5. 전체 저장소 끝
        # =================================================

        if is_collection_finished():

            log(
                "KCI OAI 마지막까지 "
                "수집 완료"
            )

            log(
                f"최종 관련 후보: "
                f"{relevant_count:,}"
            )

            break

        # =================================================
        # 다음 5만 건
        # =================================================

        log(
            f"목표 {TARGET_RELEVANT}개에 "
            f"도달하지 못함."
        )

        log(
            "저장된 resumptionToken부터 "
            "다음 수집 자동 시작"
        )

        time.sleep(
            NEXT_CYCLE_WAIT_SECONDS
        )

    print()
    print("=" * 90)
    print("자동 수집 종료")
    print("=" * 90)

    relevant_count = (
        get_relevant_count()
    )

    total_saved = (
        get_total_saved()
    )

    print(
        f"KCI 누적 저장 : "
        f"{total_saved:,}"
    )

    print(
        f"관련 후보     : "
        f"{relevant_count:,}"
    )

    print()
    print(
        "결과 JSON:"
    )

    print(
        RESULT_FILE
    )

    print()
    print(
        "로그:"
    )

    print(
        LOG_FILE
    )


if __name__ == "__main__":
    main()