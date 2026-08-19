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
TREND_BASE = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
KLINE_BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
UT = "7eea3edcaed734bea9cbfc24409ed989"

DEFAULT_SYMBOLS = [
    "1.510300", "0.159919", "1.512480", "0.159995",
    "1.588200", "1.515880", "0.159801", "1.516110",
]
TREND_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
TREND_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"
HTTP_TIMEOUT = float(os.getenv("FSIS_HTTP_TIMEOUT", "8"))
RETRIES = int(os.getenv("FSIS_HTTP_RETRIES", "3"))
WORKERS = max(1, min(3, int(os.getenv("FSIS_FETCH_WORKERS", "3"))))


def http_json(url: str):
    last = None
    for attempt in range(RETRIES):
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 FSIS-Minute-Bridge/2.0",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        })
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep((0.8 * (2 ** attempt)) + random.uniform(0, 0.35))
    raise RuntimeError(f"request failed after {RETRIES} attempts: {last!r}")


def fetch_kline(secid, session_date):
    params = {
        "secid": secid,
        "klt": "1",
        "fqt": "1",
        "beg": session_date,
        "end": session_date,
        "lmt": "240",
        "ut": UT,
        "fields1": TREND_FIELDS1,
        "fields2": KLINE_FIELDS2,
    }
    data = (http_json(KLINE_BASE + "?" + urlencode(params)).get("data") or {})
    rows = data.get("klines") or []
    if not rows:
        raise RuntimeError("kline returned empty klines")
    return data.get("name"), data.get("code"), rows, "kline"


def fetch_trends(secid):
    params = {
        "fields1": TREND_FIELDS1,
        "fields2": TREND_FIELDS2,
        "ut": UT,
        "ndays": "1",
        "iscr": "0",
        "secid": secid,
    }
    data = (http_json(TREND_BASE + "?" + urlencode(params)).get("data") or {})
    rows = data.get("trends") or []
    if not rows:
        raise RuntimeError("trends2 returned empty trends")
    return data.get("name"), data.get("code"), rows, "trends2"


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
    time.sleep(random.uniform(0.05, 0.35))
    try:
        name, code, rows, variant = fetch_kline(secid, session_date)
        bars = norm_kline(rows, fetched_at)
    except Exception as kline_error:
        name, code, rows, variant = fetch_trends(secid)
        bars = norm_trend(rows, fetched_at)
        if not bars:
            raise RuntimeError(f"trends2 empty after kline error: {kline_error!r}")
    bars, effective_cutoff, dropped = validate_pit(bars, bj_now)
    return {
        "secid": secid,
        "name": name,
        "code": code,
        "source_variant": variant,
        "latest_bar_ts": bars[-1]["ts"],
        "bar_count": len(bars),
        "bars": bars,
        "pit_cutoff_bar": effective_cutoff,
        "future_or_open_bars_dropped": dropped,
    }


def main():
    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat()
    bj_now = now.astimezone(BJ)
    session_date = bj_now.strftime("%Y%m%d")
    symbols = [s.strip() for s in os.getenv("FSIS_SYMBOLS", "").split(",") if s.strip()]
    request_id = os.getenv("FSIS_REQUEST_ID", "default-core")
    if not symbols:
        symbols = DEFAULT_SYMBOLS
        request_id = "default-core"
    symbols = list(dict.fromkeys(symbols[:25]))

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        future_map = {
            pool.submit(fetch_one, secid, session_date, fetched_at, bj_now): secid
            for secid in symbols
        }
        for future in as_completed(future_map):
            secid = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"secid": secid, "error": repr(exc)})

    results.sort(key=lambda x: symbols.index(x["secid"]))
    import pathlib
    pathlib.Path("bridge").mkdir(exist_ok=True)

    coverage = round(len(results) / len(symbols), 4) if symbols else 0.0
    future_drops = sum(x.get("future_or_open_bars_dropped", 0) for x in results)
    effective_cutoffs = [x.get("pit_cutoff_bar") for x in results if x.get("pit_cutoff_bar")]
    effective_cutoff = min(effective_cutoffs) if effective_cutoffs else None
    status_code = "FAILED" if not results else ("PARTIAL_FAILURE" if failures else "OK")
    live_eligible = bool(results) and not failures and future_drops == 0

    payload = {
        "schema": "FSIS.minute-bridge.v2",
        "provider": "eastmoney",
        "provider_endpoint_primary": KLINE_BASE,
        "provider_endpoint_fallback": TREND_BASE,
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "resolution": "1m",
        "source_mode": "public_http",
        "request_id": request_id,
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "symbols_failed": len(failures),
        "coverage_ratio": coverage,
        "pit_cutoff_bar": effective_cutoff,
        "future_or_open_bars_dropped": future_drops,
        "status": status_code,
        "live_eligible": live_eligible,
        "results": results,
        "failures": failures,
    }
    with open("bridge/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    status = {
        "schema": "FSIS.minute-bridge.status.v2",
        "provider": "eastmoney",
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "resolution": "1m",
        "request_id": request_id,
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "symbols_failed": len(failures),
        "coverage_ratio": coverage,
        "latest_bar_max": max((x["latest_bar_ts"] for x in results), default=None),
        "pit_cutoff_bar": effective_cutoff,
        "future_or_open_bars_dropped": future_drops,
        "status": status_code,
        "live_eligible": live_eligible,
        "fetch_workers": WORKERS,
        "http_timeout_seconds": HTTP_TIMEOUT,
        "retry_count": RETRIES,
    }
    with open("bridge/status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
