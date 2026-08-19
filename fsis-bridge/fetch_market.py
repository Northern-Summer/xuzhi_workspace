#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""Full A-share discovery with EastMoney primary and Tencent full-market fallback."""

import json
import os
import random
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN = os.getenv("FSIS_EASTMONEY_UT", "bd1d9ddb04089700cf9c27f6f7426281")
EM_HOSTS = [
    os.getenv("FSIS_EM_HOST_PRIMARY", "push2.eastmoney.com"),
    "82.push2.eastmoney.com",
    "99.push2.eastmoney.com",
    "80.push2.eastmoney.com",
]
TX_URL = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
TIMEOUT = float(os.getenv("FSIS_MARKET_TIMEOUT", "8"))
RETRIES = int(os.getenv("FSIS_MARKET_RETRIES", "2"))
EM_PAGE_SIZE = max(50, min(100, int(os.getenv("FSIS_MARKET_PAGE_SIZE", "100"))))
TX_PAGE_SIZE = 200
MAX_PAGES = max(10, min(100, int(os.getenv("FSIS_MARKET_MAX_PAGES", "80"))))
CANDIDATES = max(25, min(250, int(os.getenv("FSIS_MINUTE_CANDIDATES", "120"))))
MIN_UNIVERSE = max(1000, int(os.getenv("FSIS_MIN_UNIVERSE", "3500")))
A_SHARE_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f2,f3,f4,f5,f6,f7,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62,f128,f136,f140,f141,f152"


def request_json(url, params=None, headers=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 FSIS-Market/4.0", "Accept": "application/json,text/plain,*/*", "Connection": "close"})
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8", errors="strict"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep((0.5 * (2 ** attempt)) + random.uniform(0, 0.2))
    raise RuntimeError(f"request failed after {RETRIES + 1} attempts: {last!r}")


def em_json(host, params):
    return request_json(
        f"https://{host}/api/qt/clist/get",
        params,
        {"User-Agent": "Mozilla/5.0 FSIS-EastMoney/4.0", "Referer": "https://quote.eastmoney.com/", "Accept": "application/json,text/plain,*/*"},
    )


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
        "price": row.get("f2"), "change_pct": row.get("f3"), "change": row.get("f4"),
        "volume": row.get("f5"), "amount": row.get("f6"), "amplitude": row.get("f7"), "turnover": row.get("f8"),
        "high": row.get("f15"), "low": row.get("f16"), "open": row.get("f17"), "prev_close": row.get("f18"),
        "raw": row,
    }


def fetch_eastmoney():
    merged = {}
    attempts = []
    for host in EM_HOSTS:
        try:
            reported_total = None
            rows_per_page = []
            pages = 0
            for page in range(1, MAX_PAGES + 1):
                params = {"pn": page, "pz": EM_PAGE_SIZE, "po": 1, "np": 1, "ut": TOKEN, "fltt": 2, "invt": 2, "fid": "f6", "fs": A_SHARE_FILTER, "fields": FIELDS}
                body = em_json(host, params)
                data = (body.get("data") if isinstance(body, dict) else None) or {}
                rows = data.get("diff")
                if not isinstance(rows, list):
                    raise RuntimeError("missing diff list")
                total = int(data.get("total") or 0)
                reported_total = total if reported_total is None else max(reported_total, total)
                pages += 1; rows_per_page.append(len(rows))
                for row in rows:
                    item = normalize_em(row)
                    if item: merged[item["secid"]] = item
                if not rows or (reported_total and page * EM_PAGE_SIZE >= reported_total):
                    break
            attempts.append({"provider": "eastmoney", "host": host, "status": "OK", "reported_total": reported_total or len(merged), "row_count": len(merged), "pages": pages, "rows_per_page": rows_per_page})
            if len(merged) >= MIN_UNIVERSE:
                return list(merged.values()), attempts
        except Exception as exc:
            attempts.append({"provider": "eastmoney", "host": host, "status": "FAILED", "error": repr(exc)})
    return list(merged.values()), attempts


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
            market = m; code = raw_code[len(prefix):]; break
    if market is None:
        market_field = str(first(row, "market", "market_code") or "").lower()
        if market_field in {"sh", "1", "sse"}: market = 1
        elif market_field in {"sz", "0", "szse"}: market = 0
    if market is None or not code.isdigit():
        return None
    code = code.zfill(6)
    return {
        "secid": f"{market}.{code}",
        "code": code,
        "market": market,
        "name": first(row, "name", "stock_name", "stockName"),
        "price": first(row, "price", "now", "latest", "current", "last"),
        "change_pct": first(row, "percent", "changePercent", "change_pct", "pct", "changeRatio"),
        "change": first(row, "change", "priceChange", "changeValue"),
        "volume": first(row, "volume", "vol", "dealVolume"),
        "amount": first(row, "amount", "turnover", "turnoverAmount", "dealAmount"),
        "amplitude": first(row, "amplitude", "amp"),
        "turnover": first(row, "turnoverRate", "turnover_rate"),
        "raw": row,
    }


def fetch_tencent():
    merged = {}
    page_size = TX_PAGE_SIZE
    total = None
    attempts = []
    for page in range(MAX_PAGES):
        params = {"_appver": "11.17.0", "board_code": "aStock", "sort_type": "price", "direct": "down", "offset": str(page * page_size), "count": str(page_size)}
        body = request_json(TX_URL, params, {"User-Agent": "Mozilla/5.0 FSIS-Tencent-Market/1.0", "Referer": "https://stockapp.finance.qq.com/", "Accept": "application/json,text/plain,*/*"})
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("Tencent market response missing data")
        rank = data.get("rank_list") or []
        total = int(data.get("total") or total or 0)
        for row in rank:
            item = normalize_tencent(row)
            if item: merged[item["secid"]] = item
        if not rank or (total and (page + 1) * page_size >= total):
            break
    attempts.append({"provider": "tencent", "host": "proxy.finance.qq.com", "status": "OK", "reported_total": total or len(merged), "row_count": len(merged), "pages": page + 1, "page_size": page_size})
    return list(merged.values()), attempts


def rank_candidates(items):
    def num(v):
        try: return float(v)
        except (TypeError, ValueError): return 0.0
    scored = []
    for x in items:
        p, chg, amt, amp = map(num, [x.get("price"), x.get("change_pct"), x.get("amount"), x.get("amplitude")])
        score = (min(abs(chg), 12.0) * 2.0) + (min(amp, 15.0) * 0.35) + (min(amt / 1e8, 20.0) * 0.15)
        if p > 0: scored.append((score, x))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [x for _, x in scored[:CANDIDATES]]


def main():
    fetched = datetime.now(timezone.utc).isoformat()
    em_rows, em_attempts = fetch_eastmoney()
    provider_used = "eastmoney"
    source_attempts = list(em_attempts)
    universe = {x["secid"]: x for x in em_rows}

    if len(universe) < MIN_UNIVERSE:
        try:
            tx_rows, tx_attempts = fetch_tencent()
            source_attempts.extend(tx_attempts)
            if len(tx_rows) > len(universe):
                universe = {x["secid"]: x for x in tx_rows}
                provider_used = "tencent"
        except Exception as exc:
            source_attempts.append({"provider": "tencent", "host": "proxy.finance.qq.com", "status": "FAILED", "error": repr(exc)})

    universe_rows = list(universe.values())
    plausible = len(universe_rows) >= MIN_UNIVERSE
    candidates = rank_candidates(universe_rows)
    status = "OK" if plausible and candidates else ("PARTIAL_FAILURE" if universe_rows else "FAILED")
    live = plausible and bool(candidates)
    payload = {
        "schema": "FSIS.market-bridge.v6",
        "provider": provider_used,
        "fetched_at_utc": fetched,
        "status": status,
        "live_eligible": live,
        "universe_total": len(universe_rows),
        "min_universe_required": MIN_UNIVERSE,
        "candidate_count": len(candidates),
        "candidate_secids": [x["secid"] for x in candidates],
        "source_attempts": source_attempts,
        "a_share_filter": A_SHARE_FILTER,
        "batch_mode": True,
        "heterogeneous_fallback": True,
    }
    os.makedirs("bridge", exist_ok=True)
    with open("bridge/market.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/generated-request.json", "w", encoding="utf-8") as f:
        json.dump({"schema":"FSIS.minute-bridge.request.v3","request_id":f"full-market-{fetched.replace(':','').replace('.','')}","symbols":payload["candidate_secids"],"source":"full-market-discovery-v6","generated_at_utc":fetched,"source_market_status":status}, f, ensure_ascii=False, indent=2)
    print(json.dumps({k:payload.get(k) for k in ("status","live_eligible","universe_total","candidate_count","provider")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
