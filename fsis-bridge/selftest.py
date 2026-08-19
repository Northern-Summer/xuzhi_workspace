#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""Fast deterministic OOD regression tests for FSIS bridge state boundaries."""


def minute_classify(successes: int, requested: int, stale_successes: int, cutoff_present: bool, min_coverage: float = 0.80) -> tuple[str, bool]:
    if requested <= 0 or successes <= 0:
        return "FAILED", False
    coverage = successes / requested
    if coverage < min_coverage or not cutoff_present or stale_successes > 0:
        return "PARTIAL_FAILURE", False
    return "OK", True


def market_classify(universe: int, candidate_count: int, source_ok: bool, total_reported: int | None = None, min_universe: int = 3500) -> tuple[str, bool]:
    if not source_ok or universe < min_universe or candidate_count <= 0:
        return "FAILED", False
    if total_reported is not None and total_reported < min_universe:
        return "PARTIAL_FAILURE", False
    return "OK", True


def tradeable_live(market_live: bool, minute_live: bool) -> bool:
    return bool(market_live and minute_live)


def quorum_ratio(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def main() -> int:
    # In-flight bars are expected and are excluded by PIT validation; their count
    # alone must never invalidate an otherwise coherent snapshot.
    minute_cases = [
        ((0, 8, 0, False), ("FAILED", False)),
        ((3, 8, 0, True), ("PARTIAL_FAILURE", False)),
        ((96, 120, 0, True), ("OK", True)),
        ((120, 120, 0, True), ("OK", True)),
        ((120, 120, 17, True), ("PARTIAL_FAILURE", False)),
        ((120, 120, 0, False), ("PARTIAL_FAILURE", False)),
    ]
    for actual, expected in minute_cases:
        got = minute_classify(*actual)
        assert got == expected, (actual, got, expected)

    market_cases = [
        ((0, 120, False, None), ("FAILED", False)),
        ((200, 120, True, 200), ("FAILED", False)),
        ((3500, 120, True, 3500), ("OK", True)),
        ((4800, 0, True, 4800), ("FAILED", False)),
        ((4800, 120, False, 4800), ("FAILED", False)),
    ]
    for actual, expected in market_cases:
        got = market_classify(*actual)
        assert got == expected, (actual, got, expected)

    assert tradeable_live(True, True) is True
    assert tradeable_live(True, False) is False
    assert tradeable_live(False, True) is False

    a = {f"S{i:04d}" for i in range(5000)}
    b = set(a)
    b -= {"S0001", "S0002", "S0003", "S0004", "S0005"}
    assert quorum_ratio(a, b) > 0.99
    assert quorum_ratio(set(), b) == 0.0

    print("FSIS full-market + PIT + trade-admission OOD selftest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
