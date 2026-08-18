#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

DEFAULT_SYMBOLS = [
    # Broad / core ETFs
    "1.510300", "1.510500", "1.510050", "0.159919", "0.159915",
    # Semiconductor / hard-tech
    "1.512480", "0.159995", "1.588000", "1.588200",
    # AI / computing / communication themes
    "1.515880", "1.562500", "0.159801", "0.159607",
    # Robotics / advanced manufacturing proxies
    "1.516110", "1.562600", "0.159667",
    # STAR / ChiNext broad growth
    "1.588080", "1.588090", "0.159915", "1.588000",
]

FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"
FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"


def fetch_symbol(secid: str, beg: str, end: str, lmt: int = 240):
    params = {
        "secid": secid,
        "klt": "1",
        "fqt": "1",
        "beg": beg,
        "end": end,
        "lmt": str(lmt),
        "fields1": FIELDS1,
        "fields2": FIELDS2,
    }
    url = BASE + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 FSIS-Minute-Bridge/1.0"})
    with urlopen(req, timeout=15) as r:
        payload = json.loads(r.read().decode("utf-8"))
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    return {
        "secid": secid,
        "name": data.get("name"),
        "code": data.get("code"),
        "klines": klines,
        "url": url,
    }


def normalize(rows, fetched_at):
    out = []
    for row in rows:
        parts = row.split(",")
        if len(parts) < 6:
            continue
        # East Money kline layout: date, open, close, high, low, volume, amount, amplitude, change, change_pct, turnover
        try:
            out.append({
                "ts": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "amount": float(parts[6]) if len(parts) > 6 else None,
                "amplitude": float(parts[7]) if len(parts) > 7 else None,
                "change": float(parts[8]) if len(parts) > 8 else None,
                "change_pct": float(parts[9]) if len(parts) > 9 else None,
                "turnover": float(parts[10]) if len(parts) > 10 else None,
                "fetched_at": fetched_at,
            })
        except (ValueError, TypeError):
            continue
    return out


def main():
    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat()
    bj_now = now.astimezone(BJ)
    session_date = bj_now.strftime("%Y%m%d")
    symbols = [s.strip() for s in os.getenv("FSIS_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",") if s.strip()]

    results = []
    failures = []
    for secid in symbols:
        try:
            r = fetch_symbol(secid, session_date, session_date)
            bars = normalize(r["klines"], fetched_at)
            latest = bars[-1]["ts"] if bars else None
            results.append({
                "secid": secid,
                "name": r["name"],
                "code": r["code"],
                "latest_bar_ts": latest,
                "bar_count": len(bars),
                "bars": bars,
            })
        except Exception as e:
            failures.append({"secid": secid, "error": repr(e)})

    payload = {
        "schema": "FSIS.minute-bridge.v1",
        "provider": "eastmoney",
        "provider_endpoint": BASE,
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "resolution": "1m",
        "source_mode": "public_http",
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "symbols_failed": len(failures),
        "results": results,
        "failures": failures,
    }

    os.makedirs("bridge", exist_ok=True)
    with open("bridge/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    # Small status file optimized for quick recovery checks.
    status = {
        "schema": "FSIS.minute-bridge.status.v1",
        "provider": "eastmoney",
        "fetched_at_utc": fetched_at,
        "fetched_at_bj": bj_now.isoformat(),
        "session_date_bj": session_date,
        "resolution": "1m",
        "symbols_requested": len(symbols),
        "symbols_succeeded": len(results),
        "symbols_failed": len(failures),
        "latest_bar_max": max((x["latest_bar_ts"] or "" for x in results), default=None),
        "status": "OK" if results else "FAILED",
    }
    with open("bridge/status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False))
    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
