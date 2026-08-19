#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

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
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FSIS-Minute-Bridge/2.0",
    }
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
    payload = {
        "message": message,
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": BRANCH,
    }
    current = api("GET", path)
    if current and current.get("sha"):
        payload["sha"] = current["sha"]
    result = api("PUT", path, payload)
    return result.get("commit", {}).get("sha")


def main():
    with open("bridge/status.json", "r", encoding="utf-8") as f:
        current = json.load(f)

    previous = read_json("bridge/status.json") or {}
    old_last_good = {
        "fetched_at_utc": previous.get("last_good_fetched_at_utc"),
        "fetched_at_bj": previous.get("last_good_fetched_at_bj"),
        "latest_bar_max": previous.get("last_good_latest_bar_max"),
        "commit_sha": previous.get("last_good_commit_sha"),
    }

    now = datetime.now(timezone.utc).isoformat()
    live = bool(current.get("live_eligible"))
    new_latest_commit = None
    if live:
        with open("bridge/latest.json", "r", encoding="utf-8") as f:
            latest = json.load(f)
        new_latest_commit = publish_json(
            "bridge/latest.json",
            latest,
            "FSIS bridge: publish verified minute snapshot",
        )
        last_good = {
            "fetched_at_utc": current.get("fetched_at_utc"),
            "fetched_at_bj": current.get("fetched_at_bj"),
            "latest_bar_max": current.get("latest_bar_max"),
            "commit_sha": new_latest_commit,
        }
    else:
        last_good = old_last_good

    published_status = dict(current)
    published_status.update({
        "request_state": REQUEST_STATE,
        "request_reason": REQUEST_REASON,
        "published_at_utc": now,
        "last_good_snapshot_available": bool(last_good.get("fetched_at_utc")),
        "last_good_snapshot_updated": live,
        "last_good_fetched_at_utc": last_good.get("fetched_at_utc"),
        "last_good_fetched_at_bj": last_good.get("fetched_at_bj"),
        "last_good_latest_bar_max": last_good.get("latest_bar_max"),
        "last_good_commit_sha": last_good.get("commit_sha"),
    })

    # Publish the actual object that verification will read. Never publish a stale local file.
    status_commit = publish_json(
        "bridge/status.json",
        published_status,
        "FSIS bridge: publish current data status",
    )
    print(json.dumps({
        "status_commit": status_commit,
        "latest_commit": new_latest_commit,
        "status": published_status,
    }, ensure_ascii=False))

    # DATA constraints are a valid operational state, not a CI infrastructure failure.
    if not live:
        print(f"::warning::FSIS bridge data is not live-eligible: {current.get('status')} / {REQUEST_REASON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
