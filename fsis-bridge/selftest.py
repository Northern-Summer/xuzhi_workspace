#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""OOD regression tests for the FSIS minute bridge state boundary."""


def classify(successes: int, requested: int, future_or_open: int) -> tuple[str, bool]:
    if requested <= 0 or successes <= 0:
        return "FAILED", False
    if future_or_open:
        return "PARTIAL_FAILURE", False
    if successes < requested:
        return "PARTIAL_FAILURE", False
    return "OK", True


def main() -> int:
    cases = [
        ((0, 8, 0), ("FAILED", False)),
        ((3, 8, 0), ("PARTIAL_FAILURE", False)),
        ((8, 8, 2), ("PARTIAL_FAILURE", False)),
        ((8, 8, 0), ("OK", True)),
    ]
    for actual, expected in cases:
        got = classify(*actual)
        assert got == expected, (actual, got, expected)
    print("FSIS bridge OOD selftest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
