#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
TREND_BASE = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
KLINE_BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
UT = "7eea3edcaed734bea9cbfc24409ed989"

DEFAULT_SYMBOLS = ["1.510300","0.159919","1.512480","0.159995","1.588200","1.515880","0.159801","1.516110"]
TREND_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
TREND_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"


def http_json(url: str):
    last = None
    for attempt in range(4):
        req = Request(url, headers={
            "User-Agent":"Mozilla/5.0 FSIS-Minute-Bridge/1.4",
            "Referer":"https://quote.eastmoney.com/",
            "Accept":"application/json,text/plain,*/*",
            "Connection":"close",
        })
        try:
            with urlopen(req, timeout=15) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if attempt < 3:
                time.sleep(1.0 + attempt*0.75)
    raise RuntimeError(f"request failed after retries: {last!r}")


def fetch_kline(secid, session_date):
    params={"secid":secid,"klt":"1","fqt":"1","beg":session_date,"end":session_date,"lmt":"240","ut":UT,"fields1":TREND_FIELDS1,"fields2":KLINE_FIELDS2}
    data=(http_json(KLINE_BASE+"?"+urlencode(params)).get("data") or {})
    rows=data.get("klines") or []
    if not rows: raise RuntimeError("kline returned empty klines")
    return data.get("name"), data.get("code"), rows, "kline"


def fetch_trends(secid):
    params={"fields1":TREND_FIELDS1,"fields2":TREND_FIELDS2,"ut":UT,"ndays":"1","iscr":"0","secid":secid}
    data=(http_json(TREND_BASE+"?"+urlencode(params)).get("data") or {})
    rows=data.get("trends") or []
    if not rows: raise RuntimeError("trends2 returned empty trends")
    return data.get("name"), data.get("code"), rows, "trends2"


def norm_trend(rows, fetched_at):
    out=[]
    for row in rows:
        p=row.split(",")
        if len(p)<7: continue
        try:
            out.append({"ts":p[0],"open":float(p[1]),"close":float(p[2]),"high":float(p[3]),"low":float(p[4]),"volume":float(p[5]),"amount":float(p[6]),"avg_price":float(p[7]) if len(p)>7 else None,"fetched_at":fetched_at})
        except (ValueError,TypeError): pass
    return out


def norm_kline(rows, fetched_at):
    out=[]
    for row in rows:
        p=row.split(",")
        if len(p)<6: continue
        try:
            out.append({"ts":p[0],"open":float(p[1]),"close":float(p[2]),"high":float(p[3]),"low":float(p[4]),"volume":float(p[5]),"amount":float(p[6]) if len(p)>6 else None,"amplitude":float(p[7]) if len(p)>7 else None,"change_pct":float(p[8]) if len(p)>8 else None,"change":float(p[9]) if len(p)>9 else None,"turnover":float(p[10]) if len(p)>10 else None,"fetched_at":fetched_at})
        except (ValueError,TypeError): pass
    return out


def validate_pit(bars, fetched_at_bj):
    if not bars: raise RuntimeError("zero parseable bars")
    cutoff=fetched_at_bj.replace(second=0,microsecond=0)-timedelta(minutes=1)
    kept=[]; dropped=0
    for b in bars:
        try: ts=datetime.strptime(b["ts"],"%Y-%m-%d %H:%M").replace(tzinfo=BJ)
        except ValueError: continue
        if ts>cutoff: dropped+=1
        else: kept.append(b)
    if not kept: raise RuntimeError("no PIT-safe completed minute bars")
    ts=[b["ts"] for b in kept]
    if len(ts)!=len(set(ts)): raise RuntimeError("duplicate minute timestamps")
    if ts!=sorted(ts): raise RuntimeError("minute timestamps not monotonic")
    return kept, cutoff.strftime("%Y-%m-%d %H:%M"), dropped


def main():
    now=datetime.now(timezone.utc); fetched_at=now.isoformat(); bj_now=now.astimezone(BJ); session_date=bj_now.strftime("%Y%m%d")
    symbols=[s.strip() for s in os.getenv("FSIS_SYMBOLS","").split(",") if s.strip()]
    request_id=os.getenv("FSIS_REQUEST_ID","default-core")
    if not symbols: symbols=DEFAULT_SYMBOLS; request_id="default-core"
    symbols=symbols[:25]
    results=[]; failures=[]; future_drops=0; effective_cutoff=None
    for i,secid in enumerate(symbols):
        if i: time.sleep(0.9)
        try:
            try:
                name,code,rows,variant=fetch_kline(secid,session_date); bars=norm_kline(rows,fetched_at)
            except Exception as ke:
                name,code,rows,variant=fetch_trends(secid); bars=norm_trend(rows,fetched_at)
                if not bars: raise RuntimeError(f"trends2 empty after kline error: {ke!r}")
            bars,effective_cutoff,dropped=validate_pit(bars,bj_now); future_drops+=dropped
            results.append({"secid":secid,"name":name,"code":code,"source_variant":variant,"latest_bar_ts":bars[-1]["ts"],"bar_count":len(bars),"bars":bars})
        except Exception as e: failures.append({"secid":secid,"error":repr(e)})

    import pathlib; pathlib.Path("bridge").mkdir(exist_ok=True)
    with open("bridge/latest.json","w",encoding="utf-8") as f:
        json.dump({"schema":"FSIS.minute-bridge.v1","provider":"eastmoney","provider_endpoint_primary":KLINE_BASE,"provider_endpoint_fallback":TREND_BASE,"fetched_at_utc":fetched_at,"fetched_at_bj":bj_now.isoformat(),"session_date_bj":session_date,"resolution":"1m","source_mode":"public_http","request_id":request_id,"symbols_requested":len(symbols),"symbols_succeeded":len(results),"symbols_failed":len(failures),"results":results,"failures":failures},f,ensure_ascii=False,separators=(",",":"))
    status_code="FAILED" if not results else ("PARTIAL_FAILURE" if failures else "OK")
    live_eligible=bool(results) and not failures and future_drops==0
    with open("bridge/status.json","w",encoding="utf-8") as f:
        json.dump({"schema":"FSIS.minute-bridge.status.v1","provider":"eastmoney","fetched_at_utc":fetched_at,"fetched_at_bj":bj_now.isoformat(),"session_date_bj":session_date,"resolution":"1m","request_id":request_id,"symbols_requested":len(symbols),"symbols_succeeded":len(results),"symbols_failed":len(failures),"coverage_ratio":round(len(results)/len(symbols),4) if symbols else 0.0,"latest_bar_max":max((x["latest_bar_ts"] or "" for x in results),default=None),"pit_cutoff_bar":effective_cutoff,"future_or_open_bars_dropped":future_drops,"status":status_code,"live_eligible":live_eligible},f,ensure_ascii=False,indent=2)
    print(json.dumps({"request_id":request_id,"symbols_requested":len(symbols),"symbols_succeeded":len(results),"symbols_failed":len(failures),"coverage_ratio":round(len(results)/len(symbols),4) if symbols else 0.0,"pit_cutoff_bar":effective_cutoff,"future_or_open_bars_dropped":future_drops,"status":status_code,"live_eligible":live_eligible},ensure_ascii=False))
    return 0


if __name__=="__main__": raise SystemExit(main())
