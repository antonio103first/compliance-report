#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""금융위원회 기업기본정보 API로 법인기본정보를 조회해 표1·표6·창업판정을 보완한다.

사업자등록번호(우선) 또는 법인명으로 공공데이터포털 금융위 '기업기본정보'를 조회하여
설립일·법인등록번호·사업자번호·대표자·주소·업종을 가져온다. 표4(벤처/이노비즈)는
이 API로는 알 수 없다(별도 소스 필요).

준법문서 원칙: 공적 출처(금융위/전자공시 기반)에서 확인된 값만 채우며, 보고서에서
이미 추출된 값은 덮어쓰지 않는다(빈 칸만 보완). 키 미설정 시 아무 것도 바꾸지 않는다.

── 환경변수 ──
  DATA_GO_KR_CORP_KEY : data.go.kr 금융위 기업기본정보 서비스키
  CORP_API_URL        : 요청 URL (기본: GetCorpBasicInfoService_V2/getCorpOutline_V2)
"""
import os
import re
import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request

DEFAULT_URL = ("https://apis.data.go.kr/1160100/service/"
               "GetCorpBasicInfoService_V2/getCorpOutline_V2")
DEFAULT_TIMEOUT = 15


def _digits(s):
    return re.sub(r'\D', '', s or '')


def _slim(s):
    return re.sub(r'[\s()（）㈜·.,\-]|주식회사', '', s or '')


def _fmt_date(yyyymmdd):
    d = _digits(yyyymmdd)
    if len(d) == 8:
        return f"{d[0:4]}.{d[4:6]}.{d[6:8]}"
    return ''


def _items(payload):
    try:
        it = payload['response']['body']['items']['item']
        return it if isinstance(it, list) else [it]
    except Exception:
        return []


def _score(it):
    """필드가 더 많이 찬 항목을 우선(중복 스냅샷 중 best 선택)."""
    keys = ('enpEstbDt', 'crno', 'enpRprFnm', 'enpBsadr', 'sicNm', 'bzno')
    return sum(1 for k in keys if str(it.get(k, '')).strip())


def lookup(biz_no=None, corp_name=None, *, service_key=None, timeout=DEFAULT_TIMEOUT):
    """(사업자번호 우선, 없으면 법인명) → 법인기본정보 dict.

    반환 키(가능 시): establishment_date, corp_reg_number, business_registration,
    representative, address, business_description, _company_api, _warnings
    키 미설정/미조회 시 빈 dict.
    """
    key = service_key or os.environ.get('DATA_GO_KR_CORP_KEY', '')
    url = os.environ.get('CORP_API_URL', DEFAULT_URL)
    if not key:
        return {}

    params = {'serviceKey': key, 'pageNo': 1, 'numOfRows': 10, 'resultType': 'json'}
    bn = _digits(biz_no)
    if len(bn) == 10:
        params['bzno'] = bn
    elif corp_name:
        params['corpNm'] = corp_name
    else:
        return {}

    try:
        with urlopen(f"{url}?{urlencode(params)}", timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:  # noqa: BLE001
        return {'_warnings': [f'기업기본정보 조회 실패: {e}']}

    items = _items(data)
    if not items:
        return {'_warnings': ['기업기본정보: 조회 결과 없음']}

    # 사업자번호 조회면 그대로, 법인명 조회면 상호 근접 항목 우선
    if 'corpNm' in params and corp_name:
        target = _slim(corp_name)
        items = sorted(
            items,
            key=lambda it: (target not in _slim(it.get('corpNm', '')), -_score(it)))
    else:
        items = sorted(items, key=lambda it: -_score(it))
    it = items[0]

    out = {}
    if _fmt_date(it.get('enpEstbDt')):
        out['establishment_date'] = _fmt_date(it.get('enpEstbDt'))
    if str(it.get('crno', '')).strip():
        out['corp_reg_number'] = str(it['crno']).strip()
    if str(it.get('bzno', '')).strip():
        out['business_registration'] = str(it['bzno']).strip()
    if str(it.get('enpRprFnm', '')).strip():
        out['representative'] = str(it['enpRprFnm']).strip()
    addr = ' '.join(p for p in [str(it.get('enpBsadr', '')).strip(),
                                str(it.get('enpDtadr', '')).strip()] if p).strip()
    if addr:
        out['address'] = re.sub(r'\s+', ' ', addr)
    if str(it.get('sicNm', '')).strip():
        out['business_description'] = str(it['sicNm']).strip()
    out['_company_api'] = str(it.get('corpNm', '')).strip()

    warnings = []
    if corp_name and out['_company_api'] \
            and _slim(corp_name) not in _slim(out['_company_api']) \
            and _slim(out['_company_api']) not in _slim(corp_name):
        warnings.append(f"상호 불일치: 보고서={corp_name} / API={out['_company_api']}")
    if warnings:
        out['_warnings'] = warnings
    return out


# (cert dict 키 → report_data 속성명) : 빈 칸만 보완
_APPLY = ('establishment_date', 'corp_reg_number', 'business_registration',
          'representative', 'address', 'business_description')


def enrich_report(report_data, *, service_key=None, overwrite=False):
    """report_data 의 사업자번호(+회사명)로 금융위 조회 → 표1·표6·창업판정 필드 보완.

    overwrite=False(기본): 보고서에 이미 값이 있으면 유지하고 빈 칸만 채운다.
    경고 리스트 반환.
    """
    res = lookup(report_data.business_registration,
                 report_data.company_name, service_key=service_key)
    for f in _APPLY:
        v = res.get(f)
        if v and (overwrite or not getattr(report_data, f, '')):
            setattr(report_data, f, v)
    return res.get('_warnings', [])
