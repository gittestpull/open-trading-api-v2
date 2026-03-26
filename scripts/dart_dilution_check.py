#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DART dilution/overhang risk checker (Chairman A-rule).

Purpose:
- Detect (last N days) disclosures that imply dilution/financing risk:
  유상증자, CB/BW/EB, RCPS/전환우선주, 감자 등.

Data source:
- Primary: OpenDART list.json API (requires DART_API_KEY).
- Fallback (no key): prints DART search URL for manual/browser verification.

Usage:
  python3 dart_dilution_check.py --ticker 014940 --corp-name 오리엔탈정공 --days 7 --json

Exit codes:
  0: executed (risk may be HIGH/LOW/UNKNOWN)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import xml.etree.ElementTree as ET

OPENDART_API = "https://opendart.fss.or.kr/api"
DART_DOC_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"

KEYWORDS = [
    # Equity / dilution
    "유상증자",
    "무상증자",  # not always bad, but still a corporate action
    "감자",
    # Convertibles / warrants
    "전환사채",
    "신주인수권부사채",
    "교환사채",
    "cb",
    "bw",
    "eb",
    # Preferred / hybrid
    "전환우선주",
    "상환전환우선주",
    "rcps",
    # Overhang-ish
    "주식매수선택권",  # options
]

NEGATIVE_STRONG = [
    "유상증자",
    "전환사채",
    "신주인수권부사채",
    "교환사채",
    "감자",
    "상환전환우선주",
    "전환우선주",
]


@dataclass
class Finding:
    date: str
    title: str
    rcp_no: str
    url: str
    matched: List[str]


def _now_ymd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _ymd_days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")


def _cache_dir() -> Path:
    d = Path(os.path.expanduser("~")) / ".openclaw" / "cache" / "dart"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _download_corp_codes(api_key: str, cache_path: Path, max_age_hours: int = 24) -> Path:
    if cache_path.exists():
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return cache_path

    url = f"{OPENDART_API}/corpCode.xml"
    r = requests.get(url, params={"crtfc_key": api_key}, timeout=60)
    r.raise_for_status()

    # response is a zip file
    zip_path = cache_path.with_suffix(".zip")
    zip_path.write_bytes(r.content)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # usually contains CORPCODE.xml
        names = zf.namelist()
        xml_name = next((n for n in names if n.lower().endswith(".xml")), None)
        if not xml_name:
            raise RuntimeError(f"corpCode.zip has no xml: {names}")
        zf.extract(xml_name, cache_path.parent)
        extracted = cache_path.parent / xml_name
        extracted.replace(cache_path)

    try:
        zip_path.unlink(missing_ok=True)
    except Exception:
        pass

    return cache_path


def _find_corp_code_from_xml(xml_path: Path, ticker: str) -> Optional[str]:
    # corp_code XML is big; parse iteratively
    ticker = ticker.zfill(6)
    for event, elem in ET.iterparse(str(xml_path), events=("end",)):
        if elem.tag != "list":
            continue
        stock_code = (elem.findtext("stock_code") or "").strip()
        if stock_code == ticker:
            corp_code = (elem.findtext("corp_code") or "").strip()
            return corp_code or None
        elem.clear()
    return None


def _opendart_list(api_key: str, corp_code: str, days: int) -> List[Dict]:
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": _ymd_days_ago(days),
        "end_de": _now_ymd(),
        "page_count": 100,
        "sort": "date",
        "sort_mth": "desc",
    }
    r = requests.get(f"{OPENDART_API}/list.json", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "000":
        return []
    return data.get("list", []) or []


def _match_keywords(title: str) -> List[str]:
    t = title.lower()
    matched = []
    for kw in KEYWORDS:
        if kw.lower() in t:
            matched.append(kw)
    # normalize CB/BW/EB detection: sometimes appears as "CB" in parentheses
    for kw in ("cb", "bw", "eb", "rcps"):
        if re.search(rf"\b{kw}\b", t):
            if kw.upper() not in matched and kw not in matched:
                matched.append(kw.upper())
    return matched


def assess_risk(findings: List[Finding]) -> Tuple[str, str]:
    if not findings:
        return "LOW", "최근 기간 내 조달/희석 키워드 공시 미검출"

    # if any strong negative keyword matched, treat as HIGH
    for f in findings:
        for kw in f.matched:
            if kw in NEGATIVE_STRONG or kw.lower() in [x.lower() for x in NEGATIVE_STRONG]:
                return "HIGH", f"최근 공시에서 희석/조달 키워드 검출: {kw}"

    return "MEDIUM", "최근 기간 내 관련 키워드 공시 존재(정밀 확인 필요)"


def fallback_dart_search_url(corp_name: str, days: int) -> str:
    # DART site search doesn't have a simple GET for all filters; provide main search page.
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    # Provide a stable entrypoint + instructions for browser-based filtering.
    return (
        "https://dart.fss.or.kr/dsab007/main.do"
        f"  (회사명: {corp_name}, 기간: {start}~{end}, 보고서명에 유상증자/전환사채/신주인수권부사채/교환사채/감자/RCPS 키워드 확인)"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", help="6-digit stock code", default="")
    ap.add_argument("--corp-name", help="Korean corp name for fallback", default="")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    api_key = os.getenv("DART_API_KEY")

    result: Dict = {
        "ticker": args.ticker,
        "corp_name": args.corp_name,
        "days": args.days,
        "source": None,
        "risk": "UNKNOWN",
        "reason": "",
        "findings": [],
        "fallback": None,
    }

    if not api_key:
        result["source"] = "NO_KEY"
        result["risk"] = "UNKNOWN"
        result["reason"] = "DART_API_KEY 미설정(OpenDART API 사용 불가)"
        if args.corp_name:
            result["fallback"] = fallback_dart_search_url(args.corp_name, args.days)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"DART_API_KEY 미설정 → 리스크 판정: UNKNOWN")
            if result["fallback"]:
                print(f"브라우저 확인 URL: {result['fallback']}")
        return 0

    if not args.ticker:
        raise SystemExit("--ticker is required when DART_API_KEY is set")

    cache_xml = _cache_dir() / "corpCode.xml"
    try:
        _download_corp_codes(api_key, cache_xml)
        corp_code = _find_corp_code_from_xml(cache_xml, args.ticker)
        if not corp_code:
            result["source"] = "OPENDART"
            result["risk"] = "UNKNOWN"
            result["reason"] = "corp_code 매핑 실패(종목코드→corp_code)"
        else:
            disclosures = _opendart_list(api_key, corp_code, args.days)
            findings: List[Finding] = []
            for item in disclosures:
                title = (item.get("report_nm") or "").strip()
                matched = _match_keywords(title)
                if not matched:
                    continue
                rcp_no = (item.get("rcept_no") or "").strip()
                findings.append(
                    Finding(
                        date=(item.get("rcept_dt") or "").strip(),
                        title=title,
                        rcp_no=rcp_no,
                        url=DART_DOC_URL.format(rcp_no=rcp_no),
                        matched=matched,
                    )
                )

            level, reason = assess_risk(findings)
            result["source"] = "OPENDART"
            result["risk"] = level
            result["reason"] = reason
            result["findings"] = [f.__dict__ for f in findings]
    except Exception as e:
        result["source"] = "OPENDART_ERROR"
        result["risk"] = "UNKNOWN"
        result["reason"] = f"OpenDART 조회 실패: {e}"
        if args.corp_name:
            result["fallback"] = fallback_dart_search_url(args.corp_name, args.days)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{args.ticker}] DART 조달/희석 리스크: {result['risk']} — {result['reason']}")
        if result.get("findings"):
            for f in result["findings"]:
                print(f"- {f['date']} | {f['title']} | {', '.join(f['matched'])} | {f['url']}")
        if result.get("fallback"):
            print(f"브라우저 확인 URL: {result['fallback']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
