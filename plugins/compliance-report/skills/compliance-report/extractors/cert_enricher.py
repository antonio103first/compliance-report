#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사업자등록번호(+회사명)로 벤처기업·이노비즈·메인비즈 인증을 조회한다.

표4(벤처기업 등 해당여부) 자동 판정용. 공공데이터포털(data.go.kr) Open API 를
사업자등록번호를 키로 호출하고, 회사명은 결과 교차검증(상호 불일치 경고)에 쓴다.

준법문서 임의주입 금지 원칙: 공적 출처에서 확인된 값만 주입하며, 키/엔드포인트가
없으면 아무 것도 바꾸지 않는다(빈 dict 반환).

── 환경변수 ──
  DATA_GO_KR_SERVICE_KEY : data.go.kr 일반 인증키(Decoding 키 권장)
  VENTURE_API_URL        : 벤처기업확인서 API 요청 URL (활용가이드 기준, 예: https://apis.data.go.kr/.../getVntrCmpList)
  INNOBIZ_API_URL        : 혁신형중소기업(이노비즈/메인비즈) API 요청 URL (선택)
  CERT_BIZNO_PARAM       : 사업자번호 파라미터명 (기본 'bizrno')

⚠ 엔드포인트/응답 필드명은 각 API 활용가이드(예: data.go.kr/data/15106235
  벤처기업확인서)에서 확정해 위 환경변수로 주입한다. 키 발급 후 실제 응답으로 검증.
"""
import os
import re
import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request

DEFAULT_TIMEOUT = 10


def _digits(s):
    return re.sub(r'\D', '', s or '')


def _slim(s):
    return re.sub(r'[\s()（）㈜·.,\-]|주식회사', '', s or '')


def _http_json(url, timeout):
    req = Request(url, headers={'User-Agent': 'compliance-report/1.0'})
    with urlopen(req, timeout=timeout) as r:
        raw = r.read().decode('utf-8', 'replace')
    try:
        return json.loads(raw)
    except Exception:
        return {'_raw': raw}


def _items(payload):
    """data.go.kr 표준 응답(response.body.items.item)에서 item 리스트 추출."""
    try:
        body = payload['response']['body']
        items = body.get('items') or {}
        it = items.get('item') if isinstance(items, dict) else items
        if it is None:
            return []
        return it if isinstance(it, list) else [it]
    except Exception:
        # 비표준 구조: 최상위 list 또는 data 키
        if isinstance(payload, list):
            return payload
        for k in ('data', 'items', 'list'):
            v = payload.get(k) if isinstance(payload, dict) else None
            if isinstance(v, list):
                return v
        return []


def _find_expiry(item):
    """item dict 에서 유효기간/종료일 추정값(YYYY.MM.DD)을 찾는다."""
    for k, v in item.items():
        if v and re.search(r'(end|만료|종료|유효|expr|expire)', str(k), re.I):
            m = re.search(r'\d{4}[.\-]\d{1,2}[.\-]\d{1,2}', str(v))
            if m:
                return m.group(0)
    return ''


def _find_name(item):
    for k, v in item.items():
        if v and re.search(r'(상호|법인명|기업명|회사|cmpNm|corpNm|bizNm)', str(k), re.I):
            return str(v)
    return ''


def _query(url, key, bn, timeout, bizno_param):
    """공공데이터포털 표준 GET 호출 → item 리스트 반환(없으면 [])."""
    q = urlencode({
        'serviceKey': key,
        'pageNo': 1,
        'numOfRows': 10,
        'returnType': 'json',
        '_type': 'json',
        bizno_param: bn,
    })
    return _items(_http_json(f'{url}?{q}', timeout))


def lookup(biz_no, company_name='', *, service_key=None, timeout=DEFAULT_TIMEOUT):
    """(사업자번호, 회사명) → 인증 dict.

    반환 키(가능 시): is_venture('Y'/'N'), venture_expiry,
    is_innobiz('Y'/'N'), innobiz_expiry, _warnings(list)
    키/엔드포인트 미설정 시 빈 dict.
    """
    out = {}
    warnings = []
    key = service_key or os.environ.get('DATA_GO_KR_SERVICE_KEY', '')
    bn = _digits(biz_no)
    if not key or len(bn) != 10:
        return out  # 인증키 없거나 사업자번호 불완전 → 조회 생략

    bizno_param = os.environ.get('CERT_BIZNO_PARAM', 'bizrno')

    # ── 벤처기업확인서 ──
    vurl = os.environ.get('VENTURE_API_URL', '')
    if vurl:
        try:
            items = _query(vurl, key, bn, timeout, bizno_param)
            if items:
                out['is_venture'] = 'Y'
                exp = _find_expiry(items[0])
                if exp:
                    out['venture_expiry'] = exp
                nm = _find_name(items[0])
                if company_name and nm and _slim(company_name) not in _slim(nm) \
                        and _slim(nm) not in _slim(company_name):
                    warnings.append(f'벤처 상호 불일치: 보고서={company_name} / API={nm}')
            else:
                out['is_venture'] = 'N'
        except Exception as e:  # noqa: BLE001
            warnings.append(f'벤처기업 조회 실패: {e}')

    # ── 혁신형중소기업 (이노비즈/메인비즈) ──
    iurl = os.environ.get('INNOBIZ_API_URL', '')
    if iurl:
        try:
            items = _query(iurl, key, bn, timeout, bizno_param)
            if items:
                out['is_innobiz'] = 'Y'
                exp = _find_expiry(items[0])
                if exp:
                    out['innobiz_expiry'] = exp
            else:
                out['is_innobiz'] = 'N'
        except Exception as e:  # noqa: BLE001
            warnings.append(f'혁신형중소기업 조회 실패: {e}')

    if warnings:
        out['_warnings'] = warnings
    return out


# report_data 에 주입할 필드 (cert dict 키 → report_data 속성명)
_APPLY_FIELDS = ('is_venture', 'venture_expiry', 'is_innobiz', 'innobiz_expiry')


def enrich_report(report_data, *, service_key=None):
    """report_data.business_registration + company_name 으로 조회해 표4 필드를 채운다.

    조회 성공한 필드만 덮어쓴다(빈 값/미조회는 유지). 경고 리스트를 반환.
    """
    res = lookup(report_data.business_registration,
                 report_data.company_name, service_key=service_key)
    for f in _APPLY_FIELDS:
        if res.get(f):
            setattr(report_data, f, res[f])
    return res.get('_warnings', [])
