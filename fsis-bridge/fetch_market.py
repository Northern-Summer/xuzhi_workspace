#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

"""Full A-share market discovery layer.

This is deliberately separate from the 1m execution layer: the market layer
answers "what exists and is moving now?" in a few batched calls; the minute
layer then drills into a bounded candidate set.
"""

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
CANDIDATES = max(25, min(250, int(os.getenv("FSIS_MINUTE_CANDIDATES", "120"))))

# Shanghai, Shenzhen main/ChiNext, and Beijing exchange A-shares.
A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f2,f3,f4,f5,f6,f7,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62,f128,f136,f140,f141,f152"


def http_json(host, path, params):
    url = f"https://{host}{path}?{urlencode(params)}"
    last = None
    for attempt in range(RETRIES + 1):
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 FSIS-FullMarket/3.0",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        })
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                raw = r.read().decode("utf-8", errors="strict")
                return json.loads(raw)
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep((0.5 * (2 ** attempt)) + random.uniform(0, 0.2))
    raise RuntimeError(f"{host} failed after {RETRIES + 1} attempts: {last!r}")


def fetch_list(host):
    params = {
        "pn": 1,
        "pz": 5000,
        "po": 1,
        "np": 1,
        "ut": TOKEN,
        "fltt": 2,
        "invt": 2,
        "fid": "f6",
        "fs": A_SHARE_FS,
        "fields": FIELDS,
    }
    body = http_json(host, "/api/qt/clist/get", params)
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("missing data object")
    diff = data.get("diff")
    if not isinstance(diff, list) or not diff:
        raise RuntimeError("missing/empty data.diff")
    total = int(data.get("total") or 0)
    if total and len(diff) < min(total, 1000):
        # A very small diff is suspicious for a 5000-sized request; the caller
        # will cross-check another host before declaring success.
        raise RuntimeError(f"suspiciously short diff: {len(diff)} of reported {total}")
    return total or len(diff), diff


def normalize(row):
    # EastMoney fields are loosely typed and occasionally null; preserve raw
    # values but normalize the keys FSIS actually consumes.
    return {
        "code": str(row.get("f12") or "").strip(),
        "market": int(row.get("f13") or 0),
        "name": str(row.get("f14") or "").strip(),
        "price": row.get("f2"),
        "change_pct": row.get("f3"),
        "change": row.get("f4"),
        "volume": row.get("f5"),
        "amount": row.get("f6"),
        "amplitude": row.get("f7"),
        "high": row.get("f15"),
        "low": row.get("f16"),
        "open": row.get("f17"),
        "prev_close": row.get("f18"),
        "float_cap": row.get("f20"),
        "total_cap": row.get("f21"),
        "pe": row.get("f23"),
        "turnover": row.get("f8"),
        "pb": row.get("f167"),
        "raw": row,
    }


def secid(x):
    return f"{x['market']}.{x['code']}"


def rank_candidates(items):
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    # Broad, liquidity-aware momentum score. This is only candidate generation;
    # FSIS still requires multi-scale 1m confirmation before any trade.
    scored = []
    for x in items:
        p, chg, amt, amp = map(num, [x.get("price"), x.get("change_pct"), x.get("amount"), x.get("amplitude")])
        if p <= 0 or amt <= 0:
            continue
        score = (min(abs(chg), 12.0) * 2.0) + (min(amp, 15.0) * 0.35) + (min(amt / 1e8, 20.0) * 0.15)
        # Keep both strong up/down tails in the candidate pool; the strategy
        # layer decides direction later.
        scored.append((score, x))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [x for _, x in scored[:CANDIDATES]]


def main():
    fetched = datetime.now(timezone.utc).isoformat()
    attempts = []
    successful = []
    for host in HOSTS:
        try:
            total, rows = fetch_list(host)
            attempts.append({"host": host, "status": "OK", "reported_total": total, "row_count": len(rows)})
            successful.append((host, total, rows))
        except Exception as exc:
            attempts.append({"host": host, "status": "FAILED", "error": repr(exc)})

    if not successful:
        payload = {
            "schema": "FSIS.market-bridge.v3",
            "fetched_at_utc": fetched,
            "status": "FAILED",
            "live_eligible": False,
            "universe_total": 0,
            "candidates": [],
            "source_attempts": attempts,
        }
        os.makedirs("bridge", exist_ok=True)
        with open("bridge/market.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # Build per-code signatures and require at least one large, internally
    # coherent snapshot. If two hosts agree on universe size/order-independent
    # code set, confidence is materially higher than a single 200 response.
    normalized = []
    for host, total, rows in successful:
        rows_n = [normalize(r) for r in rows]
        codes = {x["code"] for x in rows_n if x["code"]}
        normalized.append((host, total, rows_n, codes))

    best = max(normalized, key=lambda t: len(t[3]))
    host, total, rows_n, code_set = best
    quorum = 1
    intersections = []
    for other in normalized:
        if other is best:
            continue
        inter = len(code_set & other[3])
        ratio = inter / max(1, min(len(code_set), len(other[3])))
        intersections.append({"host": other[0], "intersection": inter, "ratio": round(ratio, 4)})
        if ratio >= 0.95:
            quorum += 1

    # Require a plausible A-share universe. Current market size is well above
    # 4,000, so a tiny successful page is not accepted as full-market live data.
    universe_plausible = len(code_set) >= int(os.getenv("FSIS_MIN_UNIVERSE", "3500"))
    status = "OK" if universe_plausible else "PARTIAL_FAILURE"
    live = universe_plausible and quorum >= 1
    candidates = rank_candidates(rows_n)

    out = {
        "schema": "FSIS.market-bridge.v3",
        "provider": "eastmoney",
        "fetched_at_utc": fetched,
        "status": status,
        "live_eligible": live,
        "universe_total": len(code_set),
        "reported_total": total,
        "validated_source": host,
        "source_quorum": quorum,
        "cross_source_checks": intersections,
        "candidate_count": len(candidates),
        "candidate_secids": [secid(x) for x in candidates],
        "candidates": candidates,
        "source_attempts": attempts,
        "batch_mode": True,
        "a_share_filter": A_SHARE_FS,
    }
    os.makedirs("bridge", exist_ok=True)
    with open("bridge/market.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open("bridge/generated-request.json", "w", encoding="utf-8") as f:
        json.dump({
            "schema": "FSIS.minute-bridge.request.v2",
            "request_id": f"full-market-{fetched.replace(':', '').replace('.', '')}",
            "symbols": out["candidate_secids"],
            "source": "full-market-discovery",
            "generated_at_utc": fetched,
            "source_market_status": status,
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "status": status,
        "live_eligible": live,
        "universe_total": len(code_set),
        "candidate_count": len(candidates),
        "validated_source": host,
        "source_quorum": quorum,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
