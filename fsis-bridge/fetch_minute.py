#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
# OOD repair: use the currently documented public push2 token and rotate across
# EastMoney public subdomains instead of treating one host as authoritative.
UT = "bd1d9ddb04089700cf9c27f6f7426281"
EM_SNAPSHOT_HOSTS = [
    "https://push2.eastmoney.com",
    "https://80.push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
]
EM_HISTORY_HOSTS = [
    "https://push2his.eastmoney.com",
    "https://33.push2his.eastmoney.com",
]

TREND_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
TREND_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"
SNAP_FIELDS = "f12,f13,f14,f2,f3,f4,f5,f6,f7,f8,f15,f16,f17,f18"
HTTP_TIMEOUT = float(os.getenv("FSIS_HTTP_TIMEOUT", "5"))
RETRIES = int(os.getenv("FSIS_HTTP_RETRIES", "2"))
WORKERS = max(2, min(12, int(os.getenv("FSIS_FETCH_WORKERS", "8"))))
MAX_MINUTE_CANDIDATES = max(20, min(200, int(os.getenv("FSIS_MINUTE_CANDIDATES", "100"))))
MINUTE_COVERAGE_REQUIRED = float(os.getenv("FSIS_MINUTE_COVERAGE_REQUIRED", "0.80"))
A_SHARE_FILTER = "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80"


def http_json(url: str, timeout: float = HTTP_TIMEOUT):
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FSIS-Minute-Bridge/3.0",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        })
        try:
            with urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep((0.45 * (2 ** attempt)) + random.uniform(0, 0.25))
    raise RuntimeError(f"request failed after {RETRIES + 1} attempts: {last!r}")


def fetch_all_a_share_snapshot():
    """Full-market discovery: one paged bulk snapshot, not one HTTP call per symbol."""
    merged = {}
    failures = []
    for fs in ["m:1+t:2,m:1+t:23", "m:0+t:6,m:0+t:80"]:
        page = 1
        page_size = 5000
        collected = 0
        for host in EM_SNAPSHOT_HOSTS:
            try:
                while True:
                    params = {
                        "pn": str(page), "pz": str(page_size), "po": "1", "np": "1",
                        "ut": UT, "fltt": "2", "invt": "2", "fid": "f3",
                        "fs": fs, "fields": SNAP_FIELDS,
                    }
                    payload = http_json(host + "/api/qt/clist/get?" + urlencode(params), timeout=HTTP_TIMEOUT + 2)
                    data = payload.get("data") or {}
                    rows = data.get("diff") or []
                    if not rows:
                        break
                    for row in rows:
                        code = str(row.get("f12") or "").strip()
                        market = row.get("f13")
                        if not code or market not in (0, 1):
                            continue
                        secid = f"{int(market)}.{code.zfill(6)}"
                        merged[secid] = {
                            "secid": secid,
                            "code": code.zfill(6),
                            "market": int(market),
                            "name": row.get("f14"),
                            "price": row.get("f2"),
                            "change_pct": row.get("f3"),
                            "change": row.get("f4"),
                            "volume": row.get("f5"),
                            "amount": row.get("f6"),
                            "amplitude": row.get("f7"),
                            "turnover": row.get("f8"),
                            "high": row.get("f15"),
                            "low": row.get("f16"),
                            "open": row.get("f17"),
                            "preclose": row.get("f18"),
                        }
                    collected += len(rows)
                    if len(rows) < page_size:
                        break
                    page += 1
                break
            except Exception as exc:
                last = repr(exc)
                continue
        if not collected:
            failures.append({"filter": fs, "error": last if 'last' in locals() else "unknown"})
    if not merged:
        raise RuntimeError(f"all-market snapshot discovery failed: {failures!r}")
    return list(merged.values()), failures


def select_minute_candidates(universe):
    """Deep-minute layer: rank the entire market, then spend minute bandwidth where it matters."""
    requested = [s.strip() for s in os.getenv("FSIS_SYMBOLS", "").split(",") if s.strip()]
    by_id = {x["secid"]: x for x in universe}
    selected = []
    seen = set()
    for secid in requested:
        if secid in by_id and secid not in seen:
            selected.append(secid)
            seen.add(secid)

    def score(row):
        try:
            pct = abs(float(row.get("change_pct") or 0))
            amount = float(row.get("amount") or 0)
            return pct * 100.0 + min(amount / 1e9, 20.0)
        except Exception:
            return 0.0

    ranked = sorted(universe, key=score, reverse=True)
    for row in ranked:
        if len(selected) >= MAX_MINUTE_CANDIDATES:
            break
        secid = row["secid"]
        if secid not in seen:
            selected.append(secid)
            seen.add(secid)
    return selected


def fetch_kline(secid, session_date):
    params = {
        "secid": secid, "klt": "1", "fqt": "1", "beg": session_date,
        "end": session_date, "lmt": "240", "ut": UT,
        "fields1": TREND_FIELDS1, "fields2": KLINE_FIELDS2,
    }
    last = None
    for host in EM_HISTORY_HOSTS:
        try:
            data = (http_json(host + "/api/qt/stock/kline/get?" + urlencode(params)).get("data") or {})
            rows = data.get("klines") or []
            if rows:
                return data.get("name"), data.get("code"), rows, "kline"
            last = "empty klines"
        except Exception as exc:
            last = repr(exc)
    raise RuntimeError(f"kline failed across history hosts: {last}")


def fetch_trends(secid):
    params = {
        "fields1": TREND_FIELDS1, "fields2": TREND_FIELDS2, "ut": UT,
        "ndays": "1", "iscr": "0", "secid": secid,
    }
    last = None
    for host in EM_SNAPSHOT_HOSTS:
        try:
            data = (http_json(host + "/api/qt/stock/trends2/get?" + urlencode(params)).get("data") or {})
            rows = data.get("trends") or []
            if rows:
                return data.get("name"), data.get("code"), rows, "trends2"
            last = "empty trends"
        except Exception as exc:
            last = repr(exc)
    raise RuntimeError(f"trends failed across snapshot hosts: {last}")


def norm_trend(rows, fetched_at):
    out = []
    for row in rows:
        p = row.split(",")
        if len(p) < 7:
            continue
        try:
            out.append({
                "ts": p[0], "open": float(p[1]), "close": float(p[2]),
                "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]),
                "amount": float(p[6]), "avg_price": float(p[7]) if len(p) > 7 else None,
                "fetched_at": fetched_at,
            })
        except (ValueError, TypeError):
            pass
    return out


def norm_kline(rows, fetched_at):
    out = []
    for row in rows:
        p = row.split(",")
        if len(p) < 6:
            continue
        try:
            out.append({
                "ts": p[0], "open": float(p[1]), "close": float(p[2]),
                "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]),
                "amount": float(p[6]) if len(p) > 6 else None,
                "amplitude": float(p[7]) if len(p) > 7 else None,
                "change_pct": float(p[8]) if len(p) > 8 else None,
                "change": float(p[9]) if len(p) > 9 else None,
                "turnover": float(p[10]) if len(p) > 10 else None,
                "fetched_at": fetched_at,
            })
        except (ValueError, TypeError):
            pass
    return out


def validate_pit(bars, fetched_at_bj):
    if not bars:
        raise RuntimeError("zero parseable bars")
    cutoff = fetched_at_bj.replace(second=0, microsecond=0) - timedelta(minutes=1)
    kept, dropped = [], 0
    for bar in bars:
        try:
            ts = datetime.strptime(bar["ts"], "%Y-%m-%d %H:%M").replace(tzinfo=BJ)
        except ValueError:
            continue
        if ts > cutoff:
            dropped += 1
        else:
            kept.append(bar)
    if not kept:
        raise RuntimeError("no PIT-safe completed minute bars")
    timestamps = [bar["ts"] for bar in kept]
    if len(timestamps) != len(set(timestamps)):
        raise RuntimeError("duplicate minute timestamps")
    if timestamps != sorted(timestamps):
        raise RuntimeError("minute timestamps not monotonic")
    return kept, cutoff.strftime("%Y-%m-%d %H:%M"), dropped


def fetch_one(secid, session_date, fetched_at, bj_now):
    try:
        name, code, rows, variant = fetch_kline(secid, session_date)
        bars = norm_kline(rows, fetched_at)
    except Exception as kline_error:
        name, code, rows, variant = fetch_trends(secid)
        bars = norm_trend(rows, fetched_at)
        if not bars:
            raise RuntimeError(f"trends empty after kline error: {kline_error!r}")
    bars, effective_cutoff, dropped = validate_pit(bars, bj_now)
    return {
        "secid": secid, "name": name, "code": code, "source_variant": variant,
        "latest_bar_ts": bars[-1]["ts"], "bar_count": len(bars), "bars": bars,
        "pit_cutoff_bar": effective_cutoff, "future_or_open_bars_dropped": dropped,
    }


def main():
    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat()
    bj_now = now.astimezone(BJ)
    session_date = bj_now.strftime("%Y%m%d")
    request_id = os.getenv("FSIS_REQUEST_ID", "default-core")

    universe, discovery_failures = fetch_all_a_share_snapshot()
    candidates = select_minute_candidates(universe)

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        future_map = {
            pool.submit(fetch_one, secid, session_date, fetched_at, bj_now): secid
            for secid in candidates
        }
        for future in as_completed(future_map):
            secid = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"secid": secid, "error": repr(exc)})

    candidates_set = set(candidates)
    results.sort(key=lambda x: candidates.index(x["secid"]))
    minute_coverage = round(len(results) / len(candidates), 4) if candidates else 0.0
    future_drops = sum(x.get("future_or_open_bars_dropped", 0) for x in results)
    cutoffs = [x.get("pit_cutoff_bar") for x in results if x.get("pit_cutoff_bar")]
    effective_cutoff = min(cutoffs) if cutoffs else None
    status_code = "OK" if not failures and minute_coverage >= MINUTE_COVERAGE_REQUIRED else ("PARTIAL_FAILURE" if results else "FAILED")
    live_eligible = bool(universe) and minute_coverage >= MINUTE_COVERAGE_REQUIRED and future_drops == 0

    payload = {
        "schema": "FSIS.market-bridge.v3",
        "provider": "eastmoney",
        "source_mode": "full_market_snapshot_plus_ranked_1m",
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "universe_total": len(universe),
        "universe_snapshot": universe,
        "universe_discovery_failures": discovery_failures,
        "minute_candidate_total": len(candidates),
        "minute_candidates": candidates,
        "minute_results": results,
        "minute_failures": failures,
        "minute_coverage_ratio": minute_coverage,
        "pit_cutoff_bar": effective_cutoff,
        "future_or_open_bars_dropped": future_drops,
        "status": status_code,
        "live_eligible": live_eligible,
        "fetch_workers": WORKERS,
        "http_timeout_seconds": HTTP_TIMEOUT,
        "retry_count": RETRIES,
    }
    import pathlib
    pathlib.Path("bridge").mkdir(exist_ok=True)
    with open("bridge/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    status = {
        "schema": "FSIS.minute-bridge.status.v3",
        "provider": "eastmoney",
        "source_mode": "full_market_snapshot_plus_ranked_1m",
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "request_id": request_id,
        "universe_total": len(universe),
        "minute_candidate_total": len(candidates),
        "minute_succeeded": len(results),
        "minute_failed": len(failures),
        "minute_coverage_ratio": minute_coverage,
        "latest_bar_max": max((x["latest_bar_ts"] for x in results), default=None),
        "pit_cutoff_bar": effective_cutoff,
        "future_or_open_bars_dropped": future_drops,
        "status": status_code,
        "live_eligible": live_eligible,
        "fetch_workers": WORKERS,
        "http_timeout_seconds": HTTP_TIMEOUT,
        "retry_count": RETRIES,
        "discovery_failure_count": len(discovery_failures),
        "minute_coverage_required": MINUTE_COVERAGE_REQUIRED,
    }
    with open("bridge/status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
