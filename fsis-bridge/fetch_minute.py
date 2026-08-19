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
TREND_HOSTS = [os.getenv("FSIS_EM_HOST_PRIMARY", "push2.eastmoney.com"), "82.push2.eastmoney.com", "99.push2.eastmoney.com"]
KLINE_HOSTS = [os.getenv("FSIS_EM_HIS_HOST_PRIMARY", "push2his.eastmoney.com"), "33.push2his.eastmoney.com"]
TENCENT_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
UT = os.getenv("FSIS_EASTMONEY_UT", "bd1d9ddb04089700cf9c27f6f7426281")
DEFAULT_SYMBOLS = ["1.510300", "0.159919", "1.512480", "0.159995", "1.588200", "1.515880", "0.159801", "1.516110"]
TREND_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
TREND_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"
HTTP_TIMEOUT = float(os.getenv("FSIS_HTTP_TIMEOUT", "8"))
RETRIES = int(os.getenv("FSIS_HTTP_RETRIES", "2"))
WORKERS = max(2, min(10, int(os.getenv("FSIS_FETCH_WORKERS", "8"))))
MAX_SYMBOLS = max(25, min(250, int(os.getenv("FSIS_MINUTE_MAX_SYMBOLS", "120"))))
LIVE_COVERAGE = float(os.getenv("FSIS_MINUTE_LIVE_COVERAGE", "0.80"))


def request_json(url, params=None, headers=None):
    url = url if not params else f"{url}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 FSIS-Minute-Bridge/3.1", "Referer": "https://quote.eastmoney.com/", "Accept": "application/json,text/plain,*/*", "Connection": "close"})
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8", errors="strict"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep((0.45 * (2 ** attempt)) + random.uniform(0, 0.2))
    raise RuntimeError(f"request failed after {RETRIES + 1} attempts: {last!r}")


def em_json(host, path, params):
    return request_json(f"https://{host}{path}", params, {"User-Agent": "Mozilla/5.0 FSIS-Minute-Bridge/3.1", "Referer": "https://quote.eastmoney.com/", "Accept": "application/json,text/plain,*/*", "Connection": "close"})


def fetch_kline(secid, session_date):
    params = {"secid": secid, "klt": "1", "fqt": "1", "beg": session_date, "end": session_date, "lmt": "240", "ut": UT, "fields1": TREND_FIELDS1, "fields2": KLINE_FIELDS2}
    errors = []
    for host in KLINE_HOSTS:
        try:
            body = em_json(host, "/api/qt/stock/kline/get", params)
            data = (body.get("data") if isinstance(body, dict) else None) or {}
            rows = data.get("klines") or []
            if rows:
                return data.get("name"), data.get("code"), rows, "kline", host
            errors.append(f"{host}: empty klines")
        except Exception as exc:
            errors.append(f"{host}: {exc!r}")
    raise RuntimeError("kline failed: " + " | ".join(errors))


def fetch_trends(secid):
    params = {"fields1": TREND_FIELDS1, "fields2": TREND_FIELDS2, "ut": UT, "ndays": "1", "iscr": "0", "secid": secid}
    errors = []
    for host in TREND_HOSTS:
        try:
            body = em_json(host, "/api/qt/stock/trends2/get", params)
            data = (body.get("data") if isinstance(body, dict) else None) or {}
            rows = data.get("trends") or []
            if rows:
                return data.get("name"), data.get("code"), rows, "trends2", host
            errors.append(f"{host}: empty trends")
        except Exception as exc:
            errors.append(f"{host}: {exc!r}")
    raise RuntimeError("trends2 failed: " + " | ".join(errors))


def tencent_code(secid):
    market, code = secid.split(".", 1)
    if market == "1":
        return "sh" + code
    if market == "0":
        return "sz" + code
    return None


def fetch_tencent(secid, session_date, fetched_at):
    code = tencent_code(secid)
    if not code:
        raise RuntimeError("Tencent unsupported market")
    body = request_json(TENCENT_URL, {"code": code}, {"User-Agent": "Mozilla/5.0 FSIS-Tencent-Fallback/1.0", "Referer": "https://gu.qq.com/", "Accept": "application/json,text/plain,*/*"})
    if body.get("code") != 0:
        raise RuntimeError(f"Tencent response code={body.get('code')}: {body.get('msg')}")
    node = ((body.get("data") or {}).get(code) or {})
    raw = node.get("data") or []
    date = str(node.get("date") or "")
    if date and date != session_date:
        raise RuntimeError(f"Tencent wrong session date: {date} != {session_date}")
    parsed = []
    prev_vol = 0.0
    prev_amt = 0.0
    for item in raw:
        if not isinstance(item, str):
            continue
        parts = item.split()
        if len(parts) < 4:
            continue
        hhmm = parts[0]
        try:
            price = float(parts[1]); cum_vol = float(parts[2]); cum_amt = float(parts[3])
        except (ValueError, TypeError):
            continue
        if len(hhmm) != 4 or not hhmm.isdigit():
            continue
        ts = f"{session_date[:4]}-{session_date[4:6]}-{session_date[6:8]} {hhmm[:2]}:{hhmm[2:]}"
        dv = max(0.0, cum_vol - prev_vol)
        da = max(0.0, cum_amt - prev_amt)
        parsed.append({"ts": ts, "open": price, "close": price, "high": price, "low": price, "volume": dv, "amount": da, "avg_price": price, "fetched_at": fetched_at, "source_cumulative": True})
        prev_vol, prev_amt = cum_vol, cum_amt
    if not parsed:
        raise RuntimeError("Tencent returned no parseable minute rows")
    return node.get("qt", [None, None])[1] if isinstance(node.get("qt"), list) and len(node.get("qt")) > 1 else None, code, parsed, "tencent", "web.ifzq.gtimg.cn"


def norm_trend(rows, fetched_at):
    out = []
    for row in rows:
        p = row.split(",")
        if len(p) < 7:
            continue
        try:
            out.append({"ts": p[0], "open": float(p[1]), "close": float(p[2]), "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]), "amount": float(p[6]), "avg_price": float(p[7]) if len(p) > 7 else None, "fetched_at": fetched_at})
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
            out.append({"ts": p[0], "open": float(p[1]), "close": float(p[2]), "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]), "amount": float(p[6]) if len(p) > 6 else None, "amplitude": float(p[7]) if len(p) > 7 else None, "change_pct": float(p[8]) if len(p) > 8 else None, "change": float(p[9]) if len(p) > 9 else None, "turnover": float(p[10]) if len(p) > 10 else None, "fetched_at": fetched_at})
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
    time.sleep(random.uniform(0.02, 0.18))
    errors = []
    try:
        name, code, rows, variant, host = fetch_kline(secid, session_date)
        bars = norm_kline(rows, fetched_at)
    except Exception as exc:
        errors.append(f"kline: {exc!r}")
        try:
            name, code, rows, variant, host = fetch_trends(secid)
            bars = norm_trend(rows, fetched_at)
        except Exception as exc2:
            errors.append(f"trends2: {exc2!r}")
            try:
                name, code, bars, variant, host = fetch_tencent(secid, session_date, fetched_at)
            except Exception as exc3:
                errors.append(f"tencent: {exc3!r}")
                raise RuntimeError("all minute providers failed: " + " | ".join(errors))
    bars, effective_cutoff, dropped = validate_pit(bars, bj_now)
    return {"secid": secid, "name": name, "code": code, "source_variant": variant, "source_host": host, "latest_bar_ts": bars[-1]["ts"], "bar_count": len(bars), "bars": bars, "pit_cutoff_bar": effective_cutoff, "future_or_open_bars_dropped": dropped}


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
    symbols = list(dict.fromkeys(symbols[:MAX_SYMBOLS]))

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        future_map = {pool.submit(fetch_one, secid, session_date, fetched_at, bj_now): secid for secid in symbols}
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
    status_code = "FAILED" if not results else ("PARTIAL_FAILURE" if coverage < LIVE_COVERAGE else "OK")
    live_eligible = coverage >= LIVE_COVERAGE and future_drops == 0
    payload = {"schema": "FSIS.minute-bridge.v3", "provider": "heterogeneous: eastmoney+tencent", "fetched_at_utc": fetched_at, "fetched_at_bj": bj_now.isoformat(), "session_date_bj": session_date, "resolution": "1m", "source_mode": "public_http", "request_id": request_id, "symbols_requested": len(symbols), "symbols_succeeded": len(results), "symbols_failed": len(failures), "coverage_ratio": coverage, "pit_cutoff_bar": effective_cutoff, "future_or_open_bars_dropped": future_drops, "status": status_code, "live_eligible": live_eligible, "fetch_workers": WORKERS, "http_timeout_seconds": HTTP_TIMEOUT, "retry_count": RETRIES, "results": results, "failures": failures}
    with open("bridge/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/status.json", "w", encoding="utf-8") as f:
        json.dump({k: payload[k] for k in ["schema", "provider", "fetched_at_utc", "fetched_at_bj", "session_date_bj", "resolution", "request_id", "symbols_requested", "symbols_succeeded", "symbols_failed", "coverage_ratio", "pit_cutoff_bar", "future_or_open_bars_dropped", "status", "live_eligible", "fetch_workers", "http_timeout_seconds", "retry_count"]}, f, ensure_ascii=False, indent=2)
    print(json.dumps(payload["status"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
