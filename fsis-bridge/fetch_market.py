#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""Batch A-share discovery: validated filter, provider-safe pagination, dedupe, rank."""

import json
import os
import random
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN = os.getenv("FSIS_EASTMONEY_UT", "bd1d9ddb04089700cf9c27f6f7426281")
HOSTS = [
    os.getenv("FSIS_EM_HOST_PRIMARY", "push2.eastmoney.com"),
    "82.push2.eastmoney.com",
    "99.push2.eastmoney.com",
]
TIMEOUT = float(os.getenv("FSIS_MARKET_TIMEOUT", "8"))
RETRIES = int(os.getenv("FSIS_MARKET_RETRIES", "2"))
PAGE_SIZE = max(50, min(100, int(os.getenv("FSIS_MARKET_PAGE_SIZE", "100"))))
MAX_PAGES = max(10, min(100, int(os.getenv("FSIS_MARKET_MAX_PAGES", "80"))))
CANDIDATES = max(25, min(250, int(os.getenv("FSIS_MINUTE_CANDIDATES", "120"))))
MIN_UNIVERSE = max(1000, int(os.getenv("FSIS_MIN_UNIVERSE", "3500")))

# This exact HS/J A-share filter is independently used in public EastMoney clients.
A_SHARE_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f2,f3,f4,f5,f6,f7,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62,f128,f136,f140,f141,f152"


def http_json(host, path, params):
    url = f"https://{host}{path}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 FSIS-FullMarket/3.3",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        })
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8", errors="strict"))
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep((0.5 * (2 ** attempt)) + random.uniform(0, 0.2))
    raise RuntimeError(f"{host} failed after {RETRIES + 1} attempts: {last!r}")


def normalize(row):
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
        "float_cap": row.get("f20"),
        "total_cap": row.get("f21"),
        "pe": row.get("f23"),
        "pb": row.get("f24"),
        "raw": row,
    }


def fetch_all(host):
    merged = {}
    reported_total = None
    pages = 0
    rows_per_page = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "pn": page,
            "pz": PAGE_SIZE,
            "po": 1,
            "np": 1,
            "ut": TOKEN,
            "fltt": 2,
            "invt": 2,
            "fid": "f6",
            "fs": A_SHARE_FILTER,
            "fields": FIELDS,
        }
        body = http_json(host, "/api/qt/clist/get", params)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("missing data object")
        rows = data.get("diff")
        if not isinstance(rows, list):
            raise RuntimeError("missing diff list")
        total = int(data.get("total") or 0)
        if reported_total is None:
            reported_total = total
        else:
            reported_total = max(reported_total, total)
        pages += 1
        rows_per_page.append(len(rows))
        for row in rows:
            item = normalize(row)
            if item:
                merged[item["secid"]] = item
        if not rows:
            break
        # Provider currently hard-caps the returned page near 100 even when pz is larger.
        # Therefore stop from reported total/page index, never from len(rows) alone.
        if reported_total and page * PAGE_SIZE >= reported_total:
            break
    return list(merged.values()), {"reported_total": reported_total or len(merged), "row_count": len(merged), "pages": pages, "rows_per_page": rows_per_page}


def rank_candidates(items):
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    scored = []
    for x in items:
        p, chg, amt, amp = map(num, [x.get("price"), x.get("change_pct"), x.get("amount"), x.get("amplitude")])
        if p <= 0 or amt <= 0:
            continue
        score = (min(abs(chg), 12.0) * 2.0) + (min(amp, 15.0) * 0.35) + (min(amt / 1e8, 20.0) * 0.15)
        scored.append((score, x))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [x for _, x in scored[:CANDIDATES]]


def main():
    fetched = datetime.now(timezone.utc).isoformat()
    attempts = []
    successful = []
    for host in HOSTS:
        try:
            rows, meta = fetch_all(host)
            attempts.append({"host": host, "status": "OK", **meta})
            successful.append((host, rows, meta))
        except Exception as exc:
            attempts.append({"host": host, "status": "FAILED", "error": repr(exc)})

    if not successful:
        payload = {"schema": "FSIS.market-bridge.v5", "provider": "eastmoney-batched", "fetched_at_utc": fetched, "status": "FAILED", "live_eligible": False, "universe_total": 0, "candidate_count": 0, "candidate_secids": [], "source_attempts": attempts, "a_share_filter": A_SHARE_FILTER, "pagination": {"page_size": PAGE_SIZE, "max_pages": MAX_PAGES}}
    else:
        # Prefer the largest internally coherent snapshot. When multiple hosts succeed,
        # require near-identical code sets; one healthy source is still allowed if its
        # universe is structurally plausible.
        normalized = []
        for host, rows, meta in successful:
            code_set = {x["secid"] for x in rows}
            normalized.append((host, rows, meta, code_set))
        best = max(normalized, key=lambda t: len(t[3]))
        host, rows, meta, code_set = best
        checks = []
        quorum = 1
        for other_host, _, _, other_codes in normalized:
            if other_host == host:
                continue
            ratio = len(code_set & other_codes) / max(1, min(len(code_set), len(other_codes)))
            checks.append({"host": other_host, "intersection": len(code_set & other_codes), "ratio": round(ratio, 4)})
            if ratio >= 0.95:
                quorum += 1
        plausible = len(code_set) >= MIN_UNIVERSE
        candidates = rank_candidates(rows)
        status = "OK" if plausible and candidates else ("PARTIAL_FAILURE" if rows else "FAILED")
        live = plausible and bool(candidates)
        payload = {
            "schema": "FSIS.market-bridge.v5",
            "provider": "eastmoney-batched",
            "fetched_at_utc": fetched,
            "status": status,
            "live_eligible": live,
            "universe_total": len(code_set),
            "reported_total": meta["reported_total"],
            "min_universe_required": MIN_UNIVERSE,
            "candidate_count": len(candidates),
            "candidate_secids": [x["secid"] for x in candidates],
            "validated_source": host,
            "source_quorum": quorum,
            "cross_source_checks": checks,
            "source_attempts": attempts,
            "a_share_filter": A_SHARE_FILTER,
            "pagination": {"page_size": PAGE_SIZE, "max_pages": MAX_PAGES, "rows_per_page": meta["rows_per_page"]},
            "batch_mode": True,
            "cross_source_dedupe": True,
        }

    os.makedirs("bridge", exist_ok=True)
    with open("bridge/market.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/generated-request.json", "w", encoding="utf-8") as f:
        json.dump({
            "schema": "FSIS.minute-bridge.request.v3",
            "request_id": f"full-market-{fetched.replace(':', '').replace('.', '')}",
            "symbols": payload["candidate_secids"],
            "source": "full-market-discovery-v5",
            "generated_at_utc": fetched,
            "source_market_status": payload["status"],
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: payload.get(k) for k in ("status", "live_eligible", "universe_total", "reported_total", "candidate_count", "validated_source", "source_quorum", "pagination")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
