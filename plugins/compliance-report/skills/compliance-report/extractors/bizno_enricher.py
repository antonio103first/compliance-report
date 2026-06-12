# -*- coding: utf-8 -*-
"""bizno.net 기반 사업자정보 보완 모듈.

확정된 사업자등록번호를 키로 bizno.net 의 공개 기업정보를 조회하여
투심보고서·계약서에 없는 설립일·주소·대표자·법인등록번호·업종 등을 가져온다.

준법문서 임의주입 금지 규칙:
    - 상호(회사명) 검색은 동명이인이 많아 신뢰할 수 없으므로 지원하지 않는다.
    - 반드시 '확정된 사업자등록번호' 를 키로 조회한다(`bizno.net/article/{숫자}`).
    - 한국표준산업분류(KSIC) '숫자코드' 는 bizno 에 노출되지 않는다. 업종 텍스트만
      반환하며, 숫자코드는 호출측에서 별도 확인해야 한다(industry_code 미반환).

반환 dict 키(report_data 속성명과 일치):
    establishment_date, representative, address, corp_reg_number,
    business_description, (+ _source, _company_name, _industry_chain)
"""
import re

_UA = {"User-Agent": "Mozilla/5.0 (compliance-report-enricher)"}
_BASE = "https://bizno.net/article/{}"


def lookup(biz_no: str, timeout: int = 15) -> dict:
    """확정 사업자번호로 bizno.net 조회. 실패 시 빈 dict."""
    if not biz_no:
        return {}
    digits = re.sub(r"\D", "", biz_no)
    if len(digits) != 10:
        print(f"[bizno] 사업자번호 형식 오류(10자리 아님): {biz_no}")
        return {}

    try:
        import requests
    except ImportError:
        print("[bizno] requests 미설치 — 조회를 건너뜁니다.")
        return {}

    url = _BASE.format(digits)
    try:
        r = requests.get(url, headers=_UA, timeout=timeout)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"[bizno] 조회 실패: {e}")
        return {}

    # 조회 결과에 해당 사업자번호가 실제로 포함되어야 유효 (없는 번호면 빈 페이지)
    fmt = f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    if fmt not in r.text and digits not in r.text:
        print(f"[bizno] 해당 사업자번호의 등록 정보를 찾지 못했습니다: {fmt}")
        return {}

    clean = re.sub(r"<[^>]+>", " ", r.text)
    clean = re.sub(r"\s+", " ", clean)

    out = {"_source": url}

    m = re.search(r"설립일\(신고/인허가일\)\s*[:：]\s*([\d.\-]+)", clean)
    if m:
        out["establishment_date"] = m.group(1).strip().replace("-", ".").strip(".")

    m = re.search(r"대표자명\s*[:：]\s*([가-힣A-Za-z·\s]{2,20}?)\s+(?:전화번호|회사주소|사업자)", clean)
    if m:
        out["representative"] = m.group(1).strip()

    m = re.search(r"회사주소\s*[:：]\s*(.+?)\s+(?:종업원수|사업자등록번호|법인등록번호)", clean)
    if m:
        out["address"] = m.group(1).strip()

    m = re.search(r"법인등록번호\s*[:：]\s*([\d\-]{10,})", clean)
    if m:
        out["corp_reg_number"] = m.group(1).strip()

    # 업종(영위사업) — '업종 : ... 통신판매업번호' 사이
    m = re.search(r"업종\s*[:：]\s*(.+?)\s+(?:통신판매|사업자\s*현재|설립일)", clean)
    if m:
        out["business_description"] = m.group(1).strip()

    # KSIC 분류 체인(참고용, 숫자코드 아님)
    m = re.search(r"([가-힣A-Za-z]+업(?:\s*>\s*[가-힣A-Za-zㆍ·\s]+?업)+)(?=\s+업태)", clean)
    if m:
        out["_industry_chain"] = re.sub(r"\s*>\s*", " > ", m.group(1).strip())

    # 회사명(참고용)
    m = re.search(r'content="((?:주식회사\s*[^",<]+|[^",<]+\s*주식회사|[^",<]+㈜))', r.text)
    if m:
        out["_company_name"] = m.group(1).strip()

    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit("사용법: python -m extractors.bizno_enricher <사업자등록번호>")
    result = lookup(sys.argv[1])
    if not result:
        print("조회 결과 없음")
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
