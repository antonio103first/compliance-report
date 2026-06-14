#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""벤처기업·이노비즈/메인비즈 해당여부를 회사명(+주소)으로 확정해 표4를 채운다.

공개 데이터(벤처기업명단·혁신형중소기업)에는 사업자등록번호가 없고 대표자명도
마스킹되어 있어 **회사명 + 주소(시군구)** 로만 매칭한다. 준법문서 원칙상
**유일하게 매칭되고 유효기간 내인 경우에만 '적(Y)'** 으로 확정하고, 모호하면
비워 두고 경고를 남겨 담당자가 확정하게 한다.

── 데이터 소스 ──
  · 벤처기업: data.go.kr 벤처기업명단(15084581) odcloud API → 로컬 캐시(JSON)
  · 이노비즈/메인비즈: 혁신형중소기업현황(3033893) CSV (수동 다운로드)

── 환경변수 ──
  DATA_GO_KR_CORP_KEY (또는 DATA_GO_KR_VENTURE_KEY) : 벤처기업명단 캐시 갱신용 서비스키
  VENTURE_CACHE_PATH : 벤처 명단 캐시 파일 경로 (기본 ./_data/venture_list.json)
  INNOBIZ_CSV_PATH   : 혁신형중소기업 CSV 경로 (기본 ./_data/innobiz.csv)
"""
import os
import re
import csv
import json
import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

VENTURE_NS = "15084581/v1"
ODCLOUD_BASE = "https://api.odcloud.kr/api"
SWAGGER_URL = "https://infuser.odcloud.kr/oas/docs?namespace=" + VENTURE_NS

DEFAULT_VENTURE_CACHE = os.path.join(".", "_data", "venture_list.json")
DEFAULT_INNOBIZ_CSV = os.path.join(".", "_data", "innobiz.csv")


def _slim(s):
    return re.sub(r'[\s()（）㈜·.,\-]|주식회사|\(주\)', '', s or '')


def _addr_tokens(addr):
    """주소에서 시/도 + 시군구 토큰(앞 2개)을 뽑아 매칭 키로 쓴다."""
    toks = re.sub(r'[,()]', ' ', addr or '').split()
    return [t for t in toks[:2] if len(t) >= 2]


def _key():
    return (os.environ.get('DATA_GO_KR_VENTURE_KEY')
            or os.environ.get('DATA_GO_KR_CORP_KEY') or '')


def _today():
    return datetime.date.today()


def _parse_date(s):
    m = re.search(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', str(s or ''))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ───────────────────── 벤처기업명단 캐시 ─────────────────────

def _pick_venture_path(key, timeout=20):
    """swagger 의 여러 uddi 중 데이터가 가장 많은(최신) 경로를 고른다."""
    spec = json.loads(urlopen(SWAGGER_URL, timeout=timeout).read().decode('utf-8', 'replace'))
    best, best_cnt = None, -1
    for p in spec.get("paths", {}):
        q = urlencode({"page": 1, "perPage": 1, "serviceKey": key})
        try:
            d = json.loads(urlopen(f"{ODCLOUD_BASE}{p}?{q}", timeout=timeout).read().decode('utf-8', 'replace'))
            c = int(d.get("totalCount", 0))
        except Exception:
            c = 0
        if c > best_cnt:
            best, best_cnt = p, c
    return best, best_cnt


def refresh_venture_cache(cache_path=None, *, service_key=None, per_page=1000,
                          timeout=40, max_records=None):
    """벤처기업명단 전체를 받아 회사명 인덱스 JSON 으로 저장. 저장 건수 반환."""
    key = service_key or _key()
    if not key:
        raise RuntimeError("서비스키 없음 (DATA_GO_KR_CORP_KEY)")
    cache_path = cache_path or os.environ.get('VENTURE_CACHE_PATH', DEFAULT_VENTURE_CACHE)
    path, total = _pick_venture_path(key, timeout)
    if not path:
        raise RuntimeError("벤처기업명단 uddi 탐색 실패")

    recs, page = [], 1
    while True:
        q = urlencode({"page": page, "perPage": per_page, "serviceKey": key})
        d = json.loads(urlopen(f"{ODCLOUD_BASE}{path}?{q}", timeout=timeout).read().decode('utf-8', 'replace'))
        data = d.get("data", [])
        if not data:
            break
        for r in data:
            # 스냅샷마다 컬럼명이 다름(간략주소/주소(현재본사주소), 벤처유효종료일/유효종료일 등)
            # → 부분일치로 견고하게 추출
            def pick(*subs):
                for k in r:
                    kk = str(k).replace(" ", "")
                    if any(s in kk for s in subs):
                        v = str(r[k]).strip()
                        if v:
                            return v
                return ""
            recs.append({
                "name": pick("업체명", "기업명", "회사명"),
                "addr": pick("주소"),
                "type": pick("확인유형"),
                "start": pick("유효시작"),
                "end": pick("유효종료"),
            })
        if len(data) < per_page or (max_records and len(recs) >= max_records):
            break
        page += 1

    index = {}
    for r in recs:
        index.setdefault(_slim(r["name"]), []).append(r)
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"_count": len(recs), "_source": path, "index": index},
                  f, ensure_ascii=False)
    return len(recs)


def lookup_venture(name, address="", cache_path=None):
    """회사명(+주소)으로 벤처 명단 캐시를 조회. 유일·유효 매칭만 확정."""
    cache_path = cache_path or os.environ.get('VENTURE_CACHE_PATH', DEFAULT_VENTURE_CACHE)
    if not name or not os.path.exists(cache_path):
        return {}
    with open(cache_path, encoding="utf-8") as f:
        index = json.load(f).get("index", {})
    cands = index.get(_slim(name), [])
    if not cands:
        return {}  # 명단에 없음 → 미확정(기본 부 유지)
    if len(cands) > 1 and address:
        at = _addr_tokens(address)
        narrowed = [c for c in cands if at and all(t in (c["addr"] or "") for t in at)]
        if narrowed:
            cands = narrowed
    if len(cands) != 1:
        return {"_warnings": [f"벤처 명단 매칭 모호({len(cands)}건): {name} — 담당자 확인"]}
    c = cands[0]
    end = _parse_date(c["end"])
    if end and end < _today():
        return {"_warnings": [f"벤처확인 유효기간 만료({c['end']}): {name} — 담당자 확인"]}
    return {"is_venture": "Y", "venture_expiry": c["end"], "_venture_type": c["type"]}


# ───────────────────── 이노비즈/메인비즈 CSV ─────────────────────

def lookup_innobiz(name, address="", csv_path=None):
    """혁신형중소기업현황 CSV(회사명·대표·업종·지역·유효기간)에서 회사명 매칭."""
    csv_path = csv_path or os.environ.get('INNOBIZ_CSV_PATH', DEFAULT_INNOBIZ_CSV)
    if not name or not os.path.exists(csv_path):
        return {}
    target = _slim(name)
    hits = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            vals = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            nm = next((vals[k] for k in vals if k in ("사업자명", "기업명", "회사명", "업체명")), "")
            if nm and _slim(nm) == target:
                hits.append(vals)
    if not hits:
        return {}
    if len(hits) > 1 and address:
        at = _addr_tokens(address)
        narrowed = [h for h in hits
                    if at and any(t in " ".join(h.values()) for t in at)]
        if narrowed:
            hits = narrowed
    if len(hits) != 1:
        return {"_warnings": [f"이노비즈 매칭 모호({len(hits)}건): {name} — 담당자 확인"]}
    h = hits[0]
    expiry = next((h[k] for k in h if "유효" in k or "기간" in k), "")
    return {"is_innobiz": "Y", "innobiz_expiry": expiry}


# ───────────────────── 통합 ─────────────────────

def enrich_report(report_data, *, venture_cache=None, innobiz_csv=None):
    """회사명(+주소)로 벤처·이노비즈 조회 → 표4 필드(is_venture/is_innobiz) 확정.

    유일·유효 매칭만 'Y' 로 채우고, 모호/만료/미발견은 그대로 둔다(경고 반환)."""
    warnings = []
    addr = getattr(report_data, 'address', '') or ''

    v = lookup_venture(report_data.company_name, addr, venture_cache)
    if v.get("is_venture") == "Y":
        report_data.is_venture = "Y"
        if v.get("venture_expiry"):
            report_data.venture_expiry = v["venture_expiry"]
    warnings += v.get("_warnings", [])

    i = lookup_innobiz(report_data.company_name, addr, innobiz_csv)
    if i.get("is_innobiz") == "Y":
        report_data.is_innobiz = "Y"
        if i.get("innobiz_expiry"):
            report_data.innobiz_expiry = i["innobiz_expiry"]
    warnings += i.get("_warnings", [])

    return warnings


if __name__ == "__main__":  # 캐시 갱신 CLI: python -m extractors.cert_enricher refresh
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        n = refresh_venture_cache()
        print(f"벤처기업명단 캐시 저장: {n}건")
