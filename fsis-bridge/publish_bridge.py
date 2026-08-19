#!/usr/bin/env python3
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_RETRIES = 4
API_TIMEOUT = 15
REPO = os.environ["REPO"]
BRANCH = os.environ.get("BRANCH", "fsis-data")
TOKEN = os.environ["GH_TOKEN"]
REQUEST_STATE = os.environ.get("REQUEST_STATE", "DEFAULT")
REQUEST_REASON = os.environ.get("REQUEST_REASON", "")


def api(method, path, payload=None):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={urllib.parse.quote(BRANCH)}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "FSIS-Minute-Bridge/3.9"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(API_RETRIES):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404 and method == "GET":
                return None
            last = RuntimeError(f"GitHub API {method} {path} -> {exc.code}: {detail}")
        except Exception as exc:
            last = exc
        if attempt < API_RETRIES - 1:
            time.sleep(1.0 + attempt * 1.5)
    raise last or RuntimeError("GitHub API request failed")


def read_json(path):
    body = api("GET", path)
    if not body:
        return None
    return json.loads(base64.b64decode(body["content"]).decode("utf-8"))


def publish_json(path, document, message):
    raw = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    payload = {"message": message, "content": base64.b64encode(raw).decode("ascii"), "branch": BRANCH}
    current = api("GET", path)
    if current and current.get("sha"):
        payload["sha"] = current["sha"]
    result = api("PUT", path, payload)
    return result.get("commit", {}).get("sha")


def main():
    with open("bridge/status.json", "r", encoding="utf-8") as f:
        current = json.load(f)

    previous = read_json("bridge/status.json") or {}
    old_last_good = {"fetched_at_utc": previous.get("last_good_fetched_at_utc"), "fetched_at_bj": previous.get("last_good_fetched_at_bj"), "latest_bar_max": previous.get("last_good_latest_bar_max"), "commit_sha": previous.get("last_good_commit_sha")}
    now = datetime.now(timezone.utc).isoformat()

    market_commit = None
    market_live = False
    last_good_market = {"fetched_at_utc": previous.get("last_good_market_fetched_at_utc"), "universe_total": previous.get("last_good_market_universe_total"), "validated_source": previous.get("last_good_market_source"), "commit_sha": previous.get("last_good_market_commit_sha")}
    if os.path.exists("bridge/market.json"):
        with open("bridge/market.json", "r", encoding="utf-8") as f:
            market = json.load(f)
        market_live = bool(market.get("live_eligible"))
        if market_live:
            market_commit = publish_json("bridge/market.json", market, "FSIS bridge: publish verified full-market discovery")
            last_good_market = {"fetched_at_utc": market.get("fetched_at_utc"), "universe_total": market.get("universe_total"), "validated_source": market.get("validated_source"), "commit_sha": market_commit}
        else:
            market_commit = publish_json("bridge/market.json", market, "FSIS bridge: publish current full-market state")
        if os.path.exists("bridge/generated-request.json"):
            with open("bridge/generated-request.json", "r", encoding="utf-8") as f:
                generated = json.load(f)
            publish_json("bridge/generated-request.json", generated, "FSIS bridge: publish generated minute candidate request")

    minute_live = bool(current.get("live_eligible"))
    tradeable_live = minute_live and market_live
    new_latest_commit = None
    if tradeable_live:
        with open("bridge/latest.json", "r", encoding="utf-8") as f:
            latest = json.load(f)
        new_latest_commit = publish_json("bridge/latest.json", latest, "FSIS bridge: publish verified minute snapshot")
        latest_bar_max = current.get("latest_bar_max") or current.get("pit_cutoff_bar")
        last_good = {"fetched_at_utc": current.get("fetched_at_utc"), "fetched_at_bj": current.get("fetched_at_bj"), "latest_bar_max": latest_bar_max, "commit_sha": new_latest_commit}
    else:
        fallback_latest = current.get("latest_bar_max") or current.get("pit_cutoff_bar")
        last_good = dict(old_last_good)
        if not last_good.get("latest_bar_max") and fallback_latest:
            last_good["latest_bar_max"] = fallback_latest

    published_status = dict(current)
    published_status.update({
        "request_state": REQUEST_STATE,
        "request_reason": REQUEST_REASON,
        "published_at_utc": now,
        "market_live_eligible": market_live,
        "minute_live_eligible": minute_live,
        "tradeable_live_eligible": tradeable_live,
        "market_commit_sha": market_commit,
        "last_good_market_available": bool(last_good_market.get("fetched_at_utc")),
        "last_good_market_fetched_at_utc": last_good_market.get("fetched_at_utc"),
        "last_good_market_universe_total": last_good_market.get("universe_total"),
        "last_good_market_source": last_good_market.get("validated_source"),
        "last_good_market_commit_sha": last_good_market.get("commit_sha"),
        "last_good_snapshot_available": bool(last_good.get("fetched_at_utc")),
        "last_good_snapshot_updated": tradeable_live,
        "last_good_fetched_at_utc": last_good.get("fetched_at_utc"),
        "last_good_fetched_at_bj": last_good.get("fetched_at_bj"),
        "last_good_latest_bar_max": last_good.get("latest_bar_max"),
        "last_good_commit_sha": last_good.get("commit_sha"),
    })
    status_commit = publish_json("bridge/status.json", published_status, "FSIS bridge: publish current data status")
    print(json.dumps({"status_commit": status_commit, "latest_commit": new_latest_commit, "market_commit": market_commit, "status": published_status}, ensure_ascii=False))
    if not minute_live:
        print(f"::warning::FSIS minute data is not live-eligible: {current.get('status')} / {REQUEST_REASON}")
    if not market_live:
        print("::warning::FSIS full-market discovery is not live-eligible")
    if not tradeable_live:
        print("::warning::FSIS joint tradeable admission is not live-eligible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
