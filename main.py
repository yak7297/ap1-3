"""두 필터의 MAC 점수를 비교하는 콘솔 프로그램."""

import json
import math
import re
from pathlib import Path
from time import perf_counter_ns


DATA_PATH = Path(__file__).resolve().with_name("data.json")
SIZES = (3, 5, 13, 25)
EPSILON = 1e-9
REPEATS = 10
PATTERN_KEY = re.compile(r"size_([1-9][0-9]*)_([0-9]+)")
FILTER_LABELS = {"cross": "Cross", "x": "X"}
EXPECTED_LABELS = {"+": "Cross", "x": "X"}


def mac(pattern, weights):
    """크기가 같은 두 행렬에서 같은 위치의 값끼리 곱해 누적한다."""
    score = 0.0
    size = len(pattern)
    for row in range(size):
        for col in range(size):
            score += pattern[row][col] * weights[row][col]
    return score


def decide(first_score, second_score, first_label, second_label):
    if not (math.isfinite(first_score) and math.isfinite(second_score)):
        raise ValueError("MAC 점수가 유한한 범위를 벗어났습니다.")
    if abs(first_score - second_score) < EPSILON:
        return "UNDECIDED"
    return first_label if first_score > second_score else second_label


def read_matrix(label):
    print(f"\n{label} (3줄 입력, 공백 구분)")
    matrix = []
    while len(matrix) < 3:
        row_text = input(f"  {len(matrix) + 1}/3행: ")
        try:
            fields = row_text.split()
            if len(fields) != 3:
                raise ValueError
            row = [float(field) for field in fields]
            if not all(math.isfinite(value) for value in row):
                raise ValueError
        except (ValueError, OverflowError):
            print("입력 형식 오류: 각 줄에 유한한 숫자 3개를 공백으로 구분해 입력하세요.")
            continue
        matrix.append(row)
    return matrix


def time_mac(pattern, weights):
    elapsed_ns = 0
    for _ in range(REPEATS):
        before = perf_counter_ns()
        score = mac(pattern, weights)
        elapsed_ns += perf_counter_ns() - before
    return score, elapsed_ns / REPEATS / 1_000_000


def print_benchmark(sizes, sample=None):
    print(f"\n[성능 분석] MAC 1회 평균 ({REPEATS}회 측정)")
    print("크기(N×N)     평균 시간(ms)    연산 횟수(N²)")
    for size in sizes:
        if sample is None:
            pattern = [[1.0] * size for _ in range(size)]
            weights = [[0.5] * size for _ in range(size)]
        else:
            pattern, weights = sample
        _, average_ms = time_mac(pattern, weights)
        print(f"{size:>2}×{size:<2}      {average_ms:>14.6f}    {size * size:>13}")


def run_manual():
    first = read_matrix("필터 A")
    second = read_matrix("필터 B")
    print("필터 A와 B 저장 완료.")
    pattern = read_matrix("패턴")

    first_score, first_ms = time_mac(pattern, first)
    second_score, second_ms = time_mac(pattern, second)
    print("\n[MAC 결과]")
    print(f"A 점수: {first_score!r}")
    print(f"B 점수: {second_score!r}")
    print(f"연산 시간(A+B 1쌍 평균/{REPEATS}회): {first_ms + second_ms:.6f} ms")
    try:
        result = decide(first_score, second_score, "A", "B")
    except ValueError as error:
        print(f"판정: 판정 불가 ({error})")
    else:
        if result == "UNDECIDED":
            result = f"판정 불가 (|A-B| < {EPSILON:g})"
        print(f"판정: {result}")
    print_benchmark((3,), (pattern, first))


def require_object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} 항목은 JSON 객체여야 합니다.")
    return value


def validate_matrix(matrix, size, name):
    if not isinstance(matrix, list) or len(matrix) != size:
        raise ValueError(f"{name}의 행 크기 불일치 (필요한 행 수 {size})")
    normalized = []
    for number, row in enumerate(matrix, start=1):
        if not isinstance(row, list) or len(row) != size:
            raise ValueError(f"{name}의 {number}행 열 크기 불일치 (필요한 열 수 {size})")
        normalized_row = []
        for col, value in enumerate(row, start=1):
            location = f"{name}의 {number}행 {col}열"
            if type(value) not in (int, float):
                raise ValueError(f"{location}은 숫자여야 합니다.")
            try:
                number_value = float(value)
            except OverflowError as error:
                raise ValueError(f"{location}은 유한한 숫자여야 합니다.") from error
            if not math.isfinite(number_value):
                raise ValueError(f"{location}은 유한한 숫자여야 합니다.")
            normalized_row.append(number_value)
        normalized.append(normalized_row)
    return normalized


def load_filters(filters):
    loaded = {}
    errors = {}
    for size in SIZES[1:]:
        key = f"size_{size}"
        try:
            group = require_object(filters.get(key), f"filters.{key}")
            loaded[key] = {
                label: validate_matrix(group.get(raw_label), size, f"{key}.{raw_label}")
                for raw_label, label in FILTER_LABELS.items()
            }
        except ValueError as error:
            errors[key] = str(error)
            print(f"{key} 로드 오류: {error}")
        else:
            print(f"{key} 필터 로드 완료 (Cross, X)")
    return loaded, errors


def evaluate_case(case_id, case, filters, filter_errors):
    match = PATTERN_KEY.fullmatch(case_id)
    if match is None:
        raise ValueError("패턴 키는 size_{N}_{idx} 형식이어야 합니다.")
    size_text = match.group(1)
    filter_key = f"size_{size_text}"
    if filter_key in filter_errors:
        raise ValueError(f"필터 오류: {filter_errors[filter_key]}")
    if filter_key not in filters:
        raise ValueError(f"지원하지 않는 패턴 크기: {size_text}")

    size = int(size_text)
    case = require_object(case, case_id)
    pattern = validate_matrix(case.get("input"), size, "input")
    raw_expected = case.get("expected")
    if not isinstance(raw_expected, str) or raw_expected not in EXPECTED_LABELS:
        raise ValueError("expected 값은 '+' 또는 'x'여야 합니다.")
    expected = EXPECTED_LABELS[raw_expected]

    weights = filters[filter_key]
    cross_score = mac(pattern, weights["Cross"])
    x_score = mac(pattern, weights["X"])
    print(f"Cross 점수: {cross_score!r}")
    print(f"X 점수: {x_score!r}")
    result = decide(cross_score, x_score, "Cross", "X")
    if result == expected:
        print(f"판정: {result} | expected: {expected} | PASS")
        return None

    if result == "UNDECIDED":
        reason = f"동점 처리 (|Cross-X| < {EPSILON:g}, expected: {expected})"
    else:
        reason = f"판정과 expected 불일치 ({result} / {expected})"
    print(f"판정: {result} | expected: {expected} | FAIL ({reason})")
    return reason


def print_summary(total, failures):
    print("\n[결과 요약]")
    print(f"총 테스트: {total}개")
    print(f"통과: {total - len(failures)}개")
    print(f"실패: {len(failures)}개")
    if failures:
        print("실패 케이스:")
        for case_id, reason in failures:
            print(f"- {case_id}: {reason}")


def run_json(path):
    try:
        with path.open(encoding="utf-8") as file:
            data = require_object(json.load(file), "최상위")
        patterns = require_object(data.get("patterns"), "patterns")
    except (OSError, ValueError, RecursionError) as error:
        print(f"data.json 읽기 또는 스키마 오류: {error}")
        return

    print("\n[필터 로드]")
    raw_filters = data.get("filters")
    if not isinstance(raw_filters, dict):
        print("filters 항목은 JSON 객체여야 합니다.")
        raw_filters = {}
    filters, filter_errors = load_filters(raw_filters)

    print("\n[패턴 분석]")
    failures = []
    for case_id, case in patterns.items():
        print(f"\n--- {case_id} ---")
        try:
            reason = evaluate_case(case_id, case, filters, filter_errors)
        except ValueError as error:
            reason = str(error)
            print(f"FAIL ({reason})")
        if reason is not None:
            failures.append((case_id, reason))

    print_benchmark(SIZES)
    print_summary(len(patterns), failures)


def main():
    print("=== Mini NPU Simulator ===")
    print("\n[모드 선택]")
    print("1. 사용자 입력 (3×3)")
    print("2. data.json 분석")
    try:
        while True:
            mode = input("선택: ").strip()
            if mode == "1":
                run_manual()
                break
            if mode == "2":
                run_json(DATA_PATH)
                break
            print("1 또는 2를 입력하세요.")
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 종료되었습니다. 현재 작업을 마칩니다.")


if __name__ == "__main__":
    main()
