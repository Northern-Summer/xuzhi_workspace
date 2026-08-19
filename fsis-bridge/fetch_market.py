#!/usr/bin/env python3
"""Full A-share discovery with bounded latency and provider-polite fallback."""

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN = os.getenv("FSIS_EASTMONEY_UT", "bd1d9ddb04089700cf9c27f6f7426281")
EM_HOSTS = [os.getenv("FSIS_EM_HOST_PRIMARY", "push2.eastmoney.com"), "82.push2.eastmoney.com", "99.push2.eastmoney.com", "80.push2.eastmoney.com"]
TX_URL = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
TIMEOUT = float(os.getenv("FSIS_MARKET_TIMEOUT", "5"))
RETRIES = int(os.getenv("FSIS_MARKET_RETRIES", "1"))
EM_PAGE_SIZE = 100
TX_PAGE_SIZE = 200
MAX_PAGES = max(10, min(80, int(os.getenv("FSIS_MARKET_MAX_PAGES", "60"))))
PAGE_WORKERS = max(2, min(8, int(os.getenv("FSIS_MARKET_PAGE_WORKERS", "4"))))
HOST_WORKERS = max(2, min(4, int(os.getenv("FSIS_MARKET_HOST_WORKERS", "4"))))
CANDIDATES = max(25, min(250, int(os.getenv("FSIS_MINUTE_CANDIDATES", "120"))))
MIN_UNIVERSE = max(1000, int(os.getenv("FSIS_MIN_UNIVERSE", "3500")))
A_SHARE_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f2,f3,f4,f5,f6,f7,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62,f128,f136,f140,f141,f152"


def request_json(url, params=None, headers=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 FSIS-Market/5.3", "Accept": "application/json,text/plain,*/*", "Connection": "close"})
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8", errors="strict"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(0.35 + random.uniform(0, 0.15))
    raise RuntimeError(f"request failed after {RETRIES + 1} attempts: {last!r}")


def first(row, *keys):
    for key in keys:
        value = row.get(key) if isinstance(row, dict) else None
        if value not in (None, "", "-"):
            return value
    return None


def normalize_em(row):
    market = row.get("f13")
    code = str(row.get("f12") or "").strip()
    if market not in (0, 1) or not code:
        return None
    return {
        "secid": f"{int(market)}.{code.zfill(6)}",
        "code": code.zfill(6),
        "market": int(market),
        "name": str(row.get("f14") or "").strip(),
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
        "prev_close": row.get("f18"),
        "raw": row,
    }


def em_page(host, page):
    params = {"pn": page, "pz": EM_PAGE_SIZE, "po": 1, "np": 1, "ut": TOKEN, "fltt": 2, "invt": 2, "fid": "f6", "fs": A_SHARE_FILTER, "fields": FIELDS}
    body = request_json(
        f"https://{host}/api/qt/clist/get",
        params,
        {"User-Agent": "Mozilla/5.0 FSIS-EastMoney/5.0", "Referer": "https://quote.eastmoney.com/", "Accept": "application/json,text/plain,*/*"},
    )
    data = (body.get("data") if isinstance(body, dict) else None) or {}
    rows = data.get("diff")
    if not isinstance(rows, list):
        raise RuntimeError("missing diff list")
    return int(data.get("total") or 0), rows


def fetch_eastmoney_host(host, first_total, first_rows):
    merged = {}
    for row in first_rows:
        item = normalize_em(row)
        if item:
            merged[item["secid"]] = item
    target_pages = min(MAX_PAGES, max(1, (first_total + EM_PAGE_SIZE - 1) // EM_PAGE_SIZE)) if first_total else 1
    if target_pages > 1:
        with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
            futures = {pool.submit(em_page, host, page): page for page in range(2, target_pages + 1)}
            for future in as_completed(futures):
                _, rows = future.result()
                for row in rows:
                    item = normalize_em(row)
                    if item:
                        merged[item["secid"]] = item
    return list(merged.values()), {"reported_total": first_total or len(merged), "row_count": len(merged), "pages": target_pages}


def normalize_tencent(row):
    if not isinstance(row, dict):
        return None
    raw_code = str(first(row, "code", "stock_code", "symbol") or "").strip().lower()
    if not raw_code:
        return None
    market = None
    code = raw_code
    for prefix, m in (("sh", 1), ("sz", 0), ("bj", 0)):
        if raw_code.startswith(prefix):
            market = m
            code = raw_code[len(prefix):]
            break
    if market is None:
        mf = str(first(row, "market", "market_code") or "").lower()
        if mf in {"sh", "1", "sse"}:
            market = 1
        elif mf in {"sz", "0", "szse", "bj", "bse"}:
            market = 0
    if market is None or not code.isdigit():
        return None
    code = code.zfill(6)
    return {
        "secid": f"{market}.{code}",
        "code": code,
        "market": market,
        "name": first(row, "name", "stock_name", "stockName"),
        "price": first(row, "zxj", "price", "now", "latest", "current", "last", "currentPrice", "lastPrice", "latestPrice", "curPrice"),
        "change_pct": first(row, "zdf", "percent", "changePercent", "change_pct", "pct", "changeRatio", "changeRate"),
        "change": first(row, "zd", "change", "priceChange", "changeValue"),
        "volume": first(row, "volume", "vol", "dealVolume", "deal_volume"),
        "amount": first(row, "turnover", "amount", "turnoverAmount", "dealAmount", "deal_amount"),
        "amplitude": first(row, "zf", "amplitude", "amp", "amplitudeRate"),
        "turnover": first(row, "hsl", "turnoverRate", "turnover_rate"),
        "raw": row,
    }


def tx_page(page):
    params = {"_appver": "11.17.0", "board_code": "aStock", "sort_type": "price", "direct": "down", "offset": str(page * TX_PAGE_SIZE), "count": str(TX_PAGE_SIZE)}
    body = request_json(TX_URL, params, {"User-Agent": "Mozilla/5.0 FSIS-Tencent-Market/2.1", "Referer": "https://stockapp.finance.qq.com/", "Accept": "application/json,text/plain,*/*"})
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("Tencent market response missing data")
    rank = data.get("rank_list") or []
    total = int(data.get("total") or 0)
    sample_keys = sorted(str(k) for k in rank[0].keys()) if rank and isinstance(rank[0], dict) else []
    return total, rank, sample_keys


def fetch_tencent():
    total, first_rows, sample_keys = tx_page(0)
    merged = {}
    for row in first_rows:
        item = normalize_tencent(row)
        if item:
            merged[item["secid"]] = item
    target_pages = min(MAX_PAGES, max(1, (total + TX_PAGE_SIZE - 1) // TX_PAGE_SIZE)) if total else 1
    if target_pages > 1:
        with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
            futures = {pool.submit(tx_page, page): page for page in range(1, target_pages)}
            for future in as_completed(futures):
                _, rows, page_keys = future.result()
                if not sample_keys:
                    sample_keys = page_keys
                for row in rows:
                    item = normalize_tencent(row)
                    if item:
                        merged[item["secid"]] = item
    return list(merged.values()), {"provider": "tencent", "host": "proxy.finance.qq.com", "status": "OK", "reported_total": total or len(merged), "row_count": len(merged), "pages": target_pages, "page_size": TX_PAGE_SIZE, "sample_keys": sample_keys}


def rank_candidates(items):
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    scored = []
    for idx, x in enumerate(items):
        p, chg, amt, amp = map(num, [x.get("price"), x.get("change_pct"), x.get("amount"), x.get("amplitude")])
        signal = abs(chg) + abs(amp) + min(abs(amt) / 1e8, 20.0)
        if p <= 0 and signal <= 0:
            continue
        score = (min(abs(chg), 12.0) * 2.0) + (min(abs(amp), 15.0) * 0.35) + (min(abs(amt) / 1e8, 20.0) * 0.15)
        scored.append((score, -idx, x))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [x for _, __, x in scored[:CANDIDATES]]


def main():
    fetched = datetime.now(timezone.utc).isoformat()
    probe_results = []
    healthy_probes = []
    with ThreadPoolExecutor(max_workers=HOST_WORKERS) as pool:
        futures = {pool.submit(em_page, host, 1): host for host in EM_HOSTS}
        for future in as_completed(futures):
            host = futures[future]
            try:
                total, rows = future.result()
                probe = {"provider": "eastmoney", "host": host, "status": "OK", "reported_total": total, "first_page_rows": len(rows)}
                probe_results.append(probe)
                healthy_probes.append((host, total, rows))
            except Exception as exc:
                probe_results.append({"provider": "eastmoney", "host": host, "status": "FAILED", "error": repr(exc)})

    attempts = list(probe_results)
    universe = {}
    provider_used = "none"
    selected_host = None
    if healthy_probes:
        healthy_probes.sort(key=lambda x: len(x[2]), reverse=True)
        selected_host, first_total, first_rows = healthy_probes[0]
        try:
            rows, meta = fetch_eastmoney_host(selected_host, first_total, first_rows)
            universe = {x["secid"]: x for x in rows}
            provider_used = "eastmoney"
            for attempt in attempts:
                if attempt.get("host") == selected_host:
                    attempt.update(meta, selected=True)
                    break
            if len(universe) < MIN_UNIVERSE:
                raise RuntimeError(f"selected EastMoney host yielded only {len(universe)} symbols")
        except Exception as exc:
            attempts.append({"provider": "eastmoney", "host": selected_host, "status": "FAILED_DURING_PAGINATION", "error": repr(exc)})
            universe = {}

    if len(universe) < MIN_UNIVERSE:
        try:
            tx_rows, tx_meta = fetch_tencent()
            attempts.append(tx_meta)
            if len(tx_rows) > len(universe):
                universe = {x["secid"]: x for x in tx_rows}
                provider_used = "tencent"
        except Exception as exc:
            attempts.append({"provider": "tencent", "host": "proxy.finance.qq.com", "status": "FAILED", "error": repr(exc)})

    universe_rows = list(universe.values())
    plausible = len(universe_rows) >= MIN_UNIVERSE
    candidates = rank_candidates(universe_rows)
    status = "OK" if plausible and candidates else ("PARTIAL_FAILURE" if universe_rows else "FAILED")
    live = plausible and bool(candidates)
    payload = {
        "schema": "FSIS.market-bridge.v9",
        "provider": provider_used,
        "fetched_at_utc": fetched,
        "status": status,
        "live_eligible": live,
        "universe_total": len(universe_rows),
        "min_universe_required": MIN_UNIVERSE,
        "candidate_count": len(candidates),
        "candidate_secids": [x["secid"] for x in candidates],
        "validated_source": selected_host if provider_used == "eastmoney" else provider_used,
        "source_attempts": attempts,
        "a_share_filter": A_SHARE_FILTER,
        "batch_mode": True,
        "heterogeneous_fallback": True,
        "latency_control": {"host_workers": HOST_WORKERS, "page_workers": PAGE_WORKERS, "request_timeout_seconds": TIMEOUT, "retries": RETRIES, "selected_single_eastmoney_host": True},
    }
    os.makedirs("bridge", exist_ok=True)
    with open("bridge/market.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/generated-request.json", "w", encoding="utf-8") as f:
        json.dump({"schema": "FSIS.minute-bridge.request.v3", "request_id": f"full-market-{fetched.replace(':', '').replace('.', '')}", "symbols": payload["candidate_secids"], "source": "full-market-discovery-v9", "generated_at_utc": fetched, "source_market_status": status}, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: payload.get(k) for k in ("status", "live_eligible", "universe_total", "candidate_count", "provider", "validated_source", "latency_control")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
