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
import time
import datetime
from urllib.parse import urlencode
from urllib.request import urlopen, Request

VENTURE_NS = "15084581/v1"
ODCLOUD_BASE = "https://api.odcloud.kr/api"
SWAGGER_URL = "https://infuser.odcloud.kr/oas/docs?namespace=" + VENTURE_NS

# 혁신형중소기업현황(3033893): API 없음 → 데이터셋 페이지에서 zip 자동 다운로드
INNOBIZ_PAGE = "https://www.data.go.kr/tcs/dss/selectFileDataDetailView.do?publicDataPk=3033893"
INNOBIZ_DL = "https://www.data.go.kr/cmm/cmm/fileDownload.do"

DEFAULT_VENTURE_CACHE = os.path.join(".", "_data", "venture_list.json")
DEFAULT_INNOBIZ_CACHE = os.path.join(".", "_data", "innobiz.json")
_UA = {"User-Agent": "Mozilla/5.0"}


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

def refresh_innobiz_cache(cache_path=None, *, timeout=60):
    """혁신형중소기업현황(3033893) zip(이노비즈+메인비즈 CSV)을 자동 다운로드해
    회사명 인덱스 JSON 으로 저장. 인증키 불필요(공개 파일). 저장 건수 반환."""
    import io
    cache_path = cache_path or os.environ.get('INNOBIZ_CACHE_PATH', DEFAULT_INNOBIZ_CACHE)
    page = urlopen(Request(INNOBIZ_PAGE, headers=_UA), timeout=timeout).read().decode('utf-8', 'replace')
    m = re.search(r'fileDownload\.do\?atchFileId=(\w+)&fileDetailSn=(\d+)', page)
    if not m:
        raise RuntimeError("혁신형중소기업 다운로드 링크 탐색 실패")
    dl = f"{INNOBIZ_DL}?atchFileId={m.group(1)}&fileDetailSn={m.group(2)}&insertDataPrcus=N"
    raw = urlopen(Request(dl, headers=_UA), timeout=timeout).read()

    import zipfile as _zip
    z = _zip.ZipFile(io.BytesIO(raw))
    index = {}
    count = 0
    for nm in z.namelist():
        if not nm.lower().endswith('.csv'):
            continue
        cert = '메인비즈' if '경영혁신' in nm else '이노비즈'
        body = z.read(nm)
        text = None
        for enc in ('cp949', 'utf-8-sig', 'euc-kr', 'utf-8'):
            try:
                text = body.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            continue
        for row in csv.DictReader(text.splitlines()):
            r = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
            cn = next((r[k] for k in r if k in ('회사명', '기업명', '사업자명', '업체명')), '')
            if not cn:
                continue
            rep = next((r[k] for k in r if '대표' in k), '')
            region = next((r[k] for k in r if '지역' in k), '')
            expiry = next((r[k] for k in r if '만료' in k or '유효' in k or '기간' in k), '')
            index.setdefault(_slim(cn), []).append(
                {"name": cn, "rep": rep, "region": region, "expiry": expiry, "cert": cert})
            count += 1
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"_count": count, "index": index}, f, ensure_ascii=False)
    return count


def lookup_innobiz(name, address="", representative="", cache_path=None):
    """이노비즈/메인비즈 캐시에서 회사명 매칭(대표·지역으로 동명이인 보정)."""
    cache_path = cache_path or os.environ.get('INNOBIZ_CACHE_PATH', DEFAULT_INNOBIZ_CACHE)
    if not name or not os.path.exists(cache_path):
        return {}
    with open(cache_path, encoding="utf-8") as f:
        index = json.load(f).get("index", {})
    hits = index.get(_slim(name), [])
    if not hits:
        return {}
    if len(hits) > 1 and representative:
        narrowed = [h for h in hits if h.get("rep") and _slim(h["rep"]) == _slim(representative)]
        if narrowed:
            hits = narrowed
    if len(hits) > 1 and address:
        narrowed = [h for h in hits if h.get("region") and h["region"][:2] in address]
        if narrowed:
            hits = narrowed
    if len(hits) != 1:
        return {"_warnings": [f"이노비즈/메인비즈 매칭 모호({len(hits)}건): {name} — 담당자 확인"]}
    h = hits[0]
    end = _parse_date(h.get("expiry"))
    if end and end < _today():
        return {"_warnings": [f"{h['cert']} 확인기간 만료({h.get('expiry')}): {name} — 담당자 확인"]}
    return {"is_innobiz": "Y", "innobiz_expiry": h.get("expiry", ""), "_cert_type": h.get("cert")}


# ───────────────────── 통합 ─────────────────────

def _stale(path, max_age_days):
    """캐시가 없거나 max_age_days 보다 오래되면 True."""
    if not os.path.exists(path):
        return True
    return (time.time() - os.path.getmtime(path)) / 86400.0 > max_age_days


def auto_refresh(venture_cache=None, innobiz_cache=None, *, max_age_days=None):
    """캐시가 오래됐으면 자동 재다운로드. 네트워크 실패는 무시(기존 캐시 유지).

    이노비즈/메인비즈는 인증키 없이 받으며, 벤처는 키가 있을 때만 갱신한다."""
    if max_age_days is None:
        max_age_days = int(os.environ.get('CERT_CACHE_MAX_AGE_DAYS', '30'))
    vc = venture_cache or os.environ.get('VENTURE_CACHE_PATH', DEFAULT_VENTURE_CACHE)
    ic = innobiz_cache or os.environ.get('INNOBIZ_CACHE_PATH', DEFAULT_INNOBIZ_CACHE)
    msgs = []
    if _stale(ic, max_age_days):
        try:
            msgs.append(f"이노비즈/메인비즈 캐시 갱신: {refresh_innobiz_cache(ic)}건")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"이노비즈 캐시 갱신 실패(기존 사용): {e}")
    if _key() and _stale(vc, max_age_days):
        try:
            msgs.append(f"벤처 명단 캐시 갱신: {refresh_venture_cache(vc)}건")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"벤처 캐시 갱신 실패(기존 사용): {e}")
    return msgs


def enrich_report(report_data, *, venture_cache=None, innobiz_csv=None, refresh=True):
    """회사명(+주소)로 벤처·이노비즈 조회 → 표4 필드(is_venture/is_innobiz) 확정.

    refresh=True 면 캐시가 오래됐을 때 자동 재다운로드한다(주기적 최신화).
    유일·유효 매칭만 'Y' 로 채우고, 모호/만료/미발견은 그대로 둔다(경고 반환)."""
    warnings = []
    if refresh:
        warnings += auto_refresh(venture_cache, innobiz_csv)
    addr = getattr(report_data, 'address', '') or ''

    v = lookup_venture(report_data.company_name, addr, venture_cache)
    if v.get("is_venture") == "Y":
        report_data.is_venture = "Y"
        if v.get("venture_expiry"):
            report_data.venture_expiry = v["venture_expiry"]
    warnings += v.get("_warnings", [])

    i = lookup_innobiz(report_data.company_name, addr,
                       getattr(report_data, 'representative', '') or '', innobiz_csv)
    if i.get("is_innobiz") == "Y":
        report_data.is_innobiz = "Y"
        if i.get("innobiz_expiry"):
            report_data.innobiz_expiry = i["innobiz_expiry"]
    warnings += i.get("_warnings", [])

    return warnings


if __name__ == "__main__":
    # 캐시 갱신 CLI:
    #   python -m extractors.cert_enricher refresh           # 벤처+이노비즈 모두
    #   python -m extractors.cert_enricher refresh venture   # 벤처만
    #   python -m extractors.cert_enricher refresh innobiz   # 이노비즈/메인비즈만
    import sys
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        if what in ("all", "venture"):
            print(f"벤처기업명단 캐시 저장: {refresh_venture_cache()}건")
        if what in ("all", "innobiz"):
            print(f"이노비즈/메인비즈 캐시 저장: {refresh_innobiz_cache()}건")
