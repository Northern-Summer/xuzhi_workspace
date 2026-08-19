#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""Batch A-share discovery: partition, paginate, dedupe, validate, rank."""

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
PAGE_SIZE = max(500, min(5000, int(os.getenv("FSIS_MARKET_PAGE_SIZE", "5000"))))
CANDIDATES = max(25, min(250, int(os.getenv("FSIS_MINUTE_CANDIDATES", "120"))))
MIN_UNIVERSE = max(1000, int(os.getenv("FSIS_MIN_UNIVERSE", "3500")))

# Exchange partitions are deliberately separate because a broad composite fs
# expression has returned truncated/partial universes in production.
MARKET_FILTERS = {
    "sse_sz_core": ["m:1+t:2,m:1+t:23", "m:0+t:6,m:0+t:80"],
    "bse": ["m:0+t:81"],
}
FIELDS = "f2,f3,f4,f5,f6,f7,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62,f128,f136,f140,f141,f152"


def http_json(host, path, params):
    url = f"https://{host}{path}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 FSIS-FullMarket/3.2",
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


def fetch_partition(host, fs):
    merged = {}
    page = 1
    reported_total = None
    pages = 0
    while page <= 50:
        params = {
            "pn": page,
            "pz": PAGE_SIZE,
            "po": 1,
            "np": 1,
            "ut": TOKEN,
            "fltt": 2,
            "invt": 2,
            "fid": "f6",
            "fs": fs,
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
        reported_total = total if reported_total is None else max(reported_total, total)
        pages += 1
        for row in rows:
            item = normalize(row)
            if item:
                merged[item["secid"]] = item
        if not rows or len(rows) < PAGE_SIZE:
            break
        if total and page * PAGE_SIZE >= total:
            break
        page += 1
    return list(merged.values()), {
        "reported_total": reported_total or len(merged),
        "row_count": len(merged),
        "pages": pages,
    }


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
    universe = {}
    attempts = []
    partition_stats = {}

    for partition, filters in MARKET_FILTERS.items():
        partition_rows = {}
        partition_success = False
        partition_errors = []
        for fs in filters:
            done = False
            for host in HOSTS:
                try:
                    rows, meta = fetch_partition(host, fs)
                    partition_success = True
                    done = True
                    for item in rows:
                        partition_rows[item["secid"]] = item
                    attempts.append({"partition": partition, "filter": fs, "host": host, "status": "OK", **meta})
                    break
                except Exception as exc:
                    partition_errors.append({"filter": fs, "host": host, "error": repr(exc)})
                    attempts.append({"partition": partition, "filter": fs, "host": host, "status": "FAILED", "error": repr(exc)})
            if not done:
                continue
        for secid, item in partition_rows.items():
            universe[secid] = item
        partition_stats[partition] = {
            "universe_count": len(partition_rows),
            "success": partition_success,
            "errors": partition_errors,
        }

    universe_rows = list(universe.values())
    plausible = len(universe_rows) >= MIN_UNIVERSE
    candidates = rank_candidates(universe_rows)
    status = "OK" if plausible and candidates else ("PARTIAL_FAILURE" if universe_rows else "FAILED")
    live = plausible and bool(candidates)

    payload = {
        "schema": "FSIS.market-bridge.v4",
        "provider": "eastmoney-batched",
        "fetched_at_utc": fetched,
        "status": status,
        "live_eligible": live,
        "universe_total": len(universe_rows),
        "min_universe_required": MIN_UNIVERSE,
        "candidate_count": len(candidates),
        "candidate_secids": [x["secid"] for x in candidates],
        "partition_stats": partition_stats,
        "source_attempts": attempts,
        "pagination": {"page_size": PAGE_SIZE},
        "batch_mode": True,
        "cross_partition_dedupe": True,
    }
    os.makedirs("bridge", exist_ok=True)
    with open("bridge/market.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/generated-request.json", "w", encoding="utf-8") as f:
        json.dump({
            "schema": "FSIS.minute-bridge.request.v3",
            "request_id": f"full-market-{fetched.replace(':', '').replace('.', '')}",
            "symbols": payload["candidate_secids"],
            "source": "full-market-discovery-v4",
            "generated_at_utc": fetched,
            "source_market_status": status,
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: payload[k] for k in ("status", "live_eligible", "universe_total", "candidate_count", "partition_stats")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
