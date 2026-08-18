#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
TREND_BASE = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
KLINE_BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
UT = "7eea3edcaed734bea9cbfc24409ed989"

DEFAULT_SYMBOLS = [
    "1.510300",  # 沪深300ETF
    "0.159919",  # 沪深300ETF嘉实
    "1.512480",  # 半导体ETF
    "0.159995",  # 芯片ETF
    "1.588200",  # 科创芯片ETF
    "1.515880",  # 通信/AI基础设施代理
    "0.159801",  # 芯片ETF
    "1.516110",  # 机器人相关ETF代理
]

TREND_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
TREND_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"


def http_json(url: str):
    last = None
    for attempt in range(4):
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 FSIS-Minute-Bridge/1.3",
                "Referer": "https://quote.eastmoney.com/",
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            },
        )
        try:
            with urlopen(req, timeout=15) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if attempt < 3:
                time.sleep(1.0 + attempt * 0.75)
    raise RuntimeError(f"request failed after retries: {last!r}")


def fetch_kline(secid: str, session_date: str):
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
    payload = http_json(KLINE_BASE + "?" + urlencode(params))
    data = payload.get("data") or {}
    rows = data.get("klines") or []
    if not rows:
        raise RuntimeError("kline returned empty klines")
    return data.get("name"), data.get("code"), rows, "kline"


def fetch_trends(secid: str):
    params = {
        "fields1": TREND_FIELDS1,
        "fields2": TREND_FIELDS2,
        "ut": UT,
        "ndays": "1",
        "iscr": "0",
        "secid": secid,
    }
    payload = http_json(TREND_BASE + "?" + urlencode(params))
    data = payload.get("data") or {}
    rows = data.get("trends") or []
    if not rows:
        raise RuntimeError("trends2 returned empty trends")
    return data.get("name"), data.get("code"), rows, "trends2"


def normalize_trend(rows, fetched_at):
    out = []
    for row in rows:
        parts = row.split(",")
        if len(parts) < 7:
            continue
        try:
            out.append({
                "ts": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "amount": float(parts[6]),
                "avg_price": float(parts[7]) if len(parts) > 7 else None,
                "fetched_at": fetched_at,
            })
        except (ValueError, TypeError):
            continue
    return out


def normalize_kline(rows, fetched_at):
    out = []
    for row in rows:
        parts = row.split(",")
        if len(parts) < 6:
            continue
        try:
            # East Money K-line order: date, open, close, high, low,
            # volume, amount, amplitude, change_pct, change_amt, turnover.
            out.append({
                "ts": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "amount": float(parts[6]) if len(parts) > 6 else None,
                "amplitude": float(parts[7]) if len(parts) > 7 else None,
                "change_pct": float(parts[8]) if len(parts) > 8 else None,
                "change": float(parts[9]) if len(parts) > 9 else None,
                "turnover": float(parts[10]) if len(parts) > 10 else None,
                "fetched_at": fetched_at,
            })
        except (ValueError, TypeError):
            continue
    return out


def validate_bars(bars):
    if not bars:
        raise RuntimeError("zero parseable bars")
    timestamps = [b["ts"] for b in bars]
    if len(timestamps) != len(set(timestamps)):
        raise RuntimeError("duplicate minute timestamps")
    if timestamps != sorted(timestamps):
        raise RuntimeError("minute timestamps not monotonic")


def main():
    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat()
    bj_now = now.astimezone(BJ)
    session_date = bj_now.strftime("%Y%m%d")
    symbols = [s.strip() for s in os.getenv("FSIS_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",") if s.strip()]
    request_id = os.getenv("FSIS_REQUEST_ID", "default-core")

    results = []
    failures = []
    for i, secid in enumerate(symbols):
        if i:
            time.sleep(0.9)
        try:
            try:
                name, code, rows, source_variant = fetch_kline(secid, session_date)
                bars = normalize_kline(rows, fetched_at)
            except Exception as kline_error:
                name, code, rows, source_variant = fetch_trends(secid)
                bars = normalize_trend(rows, fetched_at)
                if not bars:
                    raise RuntimeError(f"trends2 empty after kline error: {kline_error!r}")
            validate_bars(bars)
            results.append({
                "secid": secid,
                "name": name,
                "code": code,
                "source_variant": source_variant,
                "latest_bar_ts": bars[-1]["ts"],
                "bar_count": len(bars),
                "bars": bars,
            })
        except Exception as e:
            failures.append({"secid": secid, "error": repr(e)})

    payload = {
        "schema": "FSIS.minute-bridge.v1",
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
        "results": results,
        "failures": failures,
    }

    import pathlib
    pathlib.Path("bridge").mkdir(exist_ok=True)
    with open("bridge/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    if not results:
        status_code = "FAILED"
    elif failures:
        status_code = "PARTIAL_FAILURE"
    else:
        status_code = "OK"

    status = {
        "schema": "FSIS.minute-bridge.status.v1",
        "provider": "eastmoney",
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "resolution": "1m",
        "request_id": request_id,
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "symbols_failed": len(failures),
        "coverage_ratio": (len(results) / len(symbols)) if symbols else 0.0,
        "latest_bar_max": max((x["latest_bar_ts"] or "" for x in results), default=None),
        "status": status_code,
        "live_eligible": bool(results) and not failures,
    }
    with open("bridge/status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
