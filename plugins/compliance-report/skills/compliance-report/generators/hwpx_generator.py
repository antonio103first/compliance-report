"""준법사항체크리스트 HWPX 파일 생성 모듈.
실제 양식 HWPX를 복사하여 section0.xml의 placeholder를 치환.
작성지침에 따라 표1~5를 자동으로 채운다."""
import os
import re
import zipfile
from datetime import datetime, date


DEFAULT_TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "(양식) 준법사항체크리스트.hwpx"
)


def generate_hwpx_checklist(contract_data, report_data, output_path: str,
                             template_path: str = None):
    """양식 HWPX를 복사하여 준법사항체크리스트를 생성한다."""
    template_path = template_path or DEFAULT_TEMPLATE
    if not os.path.exists(template_path):
        print(f"[ERROR] HWPX 양식 파일을 찾을 수 없습니다: {template_path}")
        return

    cd = contract_data
    rd = report_data
    replacements = _build_all_replacements(cd, rd)
    warnings = _check_mismatches(cd, rd)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    _copy_and_replace(template_path, output_path, replacements)

    print(f"[OK] HWPX 준법사항체크리스트 생성 완료: {output_path}")
    if warnings:
        print(f"\n[주의] HWPX {len(warnings)}건의 불일치 발견:")
        for note in warnings:
            print(f"  - {note}")


def _build_all_replacements(cd, rd) -> dict:
    """작성지침에 따라 모든 placeholder → 실제 값 매핑을 구성."""

    # ── 기본 데이터 준비 ──
    company = rd.company_name or cd.company_name
    short = company
    if '주식회사' in company:
        short = "㈜" + company.replace('주식회사', '').replace('㈜', '').strip()
    if not short.startswith('㈜') and '㈜' not in short and '(주)' not in short:
        short = "㈜" + short

    rep = rd.representative or cd.representative or ""
    addr = rd.address or cd.address or ""
    biz_id = rd.business_registration or ""
    stock_type = cd.stock_type or rd.stock_type or ""
    inv_amt = _fmt_won(cd.total_investment)
    iss_price = _fmt_won(cd.issue_price)
    ratio = rd.share_ratio or ""
    discoverer = rd.discoverer or ""
    reviewer = rd.reviewer or ""
    post_mgr = rd.post_manager or ""

    # ── 표2: 주요 투자조건 ──
    cond_parts = []
    if cd.duration:
        cond_parts.append(f" - 존속기간 : {cd.duration}")
    if cd.redemption_terms:
        cond_parts.append(f" - 상환조건 : {cd.redemption_terms}")
    if cd.conversion_terms:
        cond_parts.append(f" - 전환조건 : {cd.conversion_terms}")
    extras = []
    if cd.refixing_terms:
        extras.append(cd.refixing_terms.replace("Refixing: ", ""))
    if cd.other_terms:
        extras.append(cd.other_terms)
    if getattr(cd, 'special_terms', ''):
        extras.append(f"특약사항: {cd.special_terms}")
    if extras:
        cond_parts.append(f" - 기타 : {', '.join(extras)} 등")
    cond_text = " ".join(cond_parts)

    # ── 표2: 위약벌 ──
    pen_parts = []
    if cd.penalty_rate:
        pen_parts.append(f" - 위약벌 : 투자금의 {cd.penalty_rate}%")
    if cd.delay_rate:
        pen_parts.append(f" - 지연배상금 : 실제 지급일까지 연 {cd.delay_rate}%")
    if cd.buyback_rate:
        pen_parts.append(f" - 주식매수청구권 : 투자원금 및 {cd.buyback_rate}%")
    pen_text = " ".join(pen_parts)

    # ── 표4: 벤처기업 등 해당여부 (검토결과: 적/부 中 하나, 미확정이면 공란) ──
    # 3-state 값 "Y"(적)/"N"(부)/""(공란). 각 행은 셀 단위로 하나만 표시.
    estab_str = rd.establishment_date or "0000년 00월 00일"
    # 창업기업: 설립일 알면 7년 기준 적/부, 모르면 공란
    if rd.establishment_date:
        startup_state = "Y" if "적" in _check_startup(rd.establishment_date) else "N"
    else:
        startup_state = ""
    # 벤처/이노비즈: cert_enricher 가 채운 3-state(Y/N/"") 그대로 사용
    venture_state = rd.is_venture if rd.is_venture in ("Y", "N") else ""
    innobiz_state = rd.is_innobiz if rd.is_innobiz in ("Y", "N") else ""

    # ── 표5: 준법사항 (적/부 판단) ──
    # 이해관계인 (계약서에서)
    interested = cd.interested_party or cd.representative or rep
    # 산업분류코드 — 한컴이 셀 형식을 검증하므로 미상값은 빈칸으로 둔다(비정형 마커 금지).
    ind_code = rd.industry_code or ""
    ind_desc = rd.business_description or ""
    # 비고란 KSIC 라벨 뒤 문자열: 코드/업종이 있을 때만 채우고, 없으면 라벨만.
    _ksic_val = " ".join(p for p in [f"({ind_code})" if ind_code else "", ind_desc] if p).strip()
    ksic_line = f'한국표준산업분류코드 : {_ksic_val}'.rstrip()
    # 주목적투자 해당여부
    purpose_transport = _yn(rd.purpose_transport)
    purpose_mobility = _yn(rd.purpose_mobility)
    purpose_south = _yn(rd.purpose_south)
    purpose_tcb = _yn(rd.purpose_tcb)
    # 제61조1항1호 IBK(별첨5): 추출값 있으면 그에 따르고, 없으면 기존 기본 '적'
    ibk_yn = _yn(rd.purpose_ibk) if rd.purpose_ibk else "적"
    # 투자구분 (신규/구주)
    is_new_stock = "신규" in (rd.investment_type or "") or "신주" in (cd.stock_type or "")
    # 해외투자 여부 (국내 주소면 부)
    is_domestic = bool(re.search(r'서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충|전|경|제주', addr))
    # 투자기간 이내 (2029.9.8 이전)
    invest_in_period = "적" if _is_before_deadline() else "부"

    # ── 표5 준법사항: 적/부 순서 목록 (양식의 실제 칼럼 빈 셀 순서) ──
    committee_date = rd.committee_date or "(확인 필요)"

    # 투자방법 판단 (제34조1항 비고 '투자방법' 5개 항목 매칭)
    stock_lower = (cd.stock_type or rd.stock_type or "").replace(" ", "")
    _su = stock_lower.upper()
    is_stock_type = any(kw in stock_lower for kw in ['보통주', '우선주', 'RCPS', 'CPS'])
    is_cb_bw = any(kw in _su for kw in ['CB', 'BW']) \
        or any(kw in stock_lower for kw in ['전환사채', '신주인수권', '교환사채'])
    is_safe = 'SAFE' in _su or '조건부지분' in stock_lower
    is_project = '프로젝트' in stock_lower

    table5_yn = [
        # ── 법령상 투자제한 (12개) ──
        "부",    # 자기 또는 제3자의 이익을 위한 조합 재산 사용 여부
        "부",    # 투자기업의 상호출자제한기업집단 소속 여부
        "부",    # 투자 제한업종 해당 여부
        "부",    # 취득 대상이 금융회사 등 주식 또는 지분인지 여부
        "부",    # 취득 대상이 이해관계인이 발행하거나 소유한 주식
        "부",    # 이해관계인에 대한 신용공여 행위 여부
        "부",    # 조합 명의로 제3자를 위하여 주식 취득/자금 중개
        "부",    # 조합이 투자한 업체로부터 차입
        "부",    # 투자계약서에 기재된 조건 외에 별도 투자조건 설정
        "적" if is_domestic else "부",  # 해외투자 요건 준수 여부
        "적",    # 2개 이상 기업 프로젝트 (확인 필요)
        "부",    # 기타 법령 위반 여부
        # ── 규약상 투자제한 ──
        "적",    # 제34조 제1항의 법상 의무투자 해당여부
        purpose_transport,   # 제35조 제1항 제1호 (국토교통분야)
        purpose_mobility,    # 제35조 제1항 제2호 (혁신성장 모빌리티)
        purpose_south,       # 제35조 제1항 제3호 (남부권 전략산업)
        ibk_yn,              # 제61조 제1항 제1호 (IBK 신규/기존거래, 별첨5)
        purpose_tcb,         # 제61조 제1항 제2호 (TCB Ti-6 등급)
        "적",    # 제34조 제3항 동일기업 동일 프로젝트
        "적",    # 제34조 제4항 후행투자 (담당자 확인)
        "부" if is_new_stock else "적",  # 제34조 제2항 구주
        "부" if is_domestic else "적",   # 제34조 제2항 해외투자
        "부",    # 제34조 제8항 자금 대여 방식
        "부",    # 제34조 제10항 금지행위 (담당자 확인)
        invest_in_period,  # 제4조 제26호 투자기간 이내
        "적",    # 제8조 제5항 납입금액 충족
        "부",    # 제34조의2 이해상충 검토
        "적",    # 제37조 투자심의위원회 부의
        "적",    # 제61조 제14항 볼커룰
    ]

    # ── 투자방법 (O) 체크 ──
    # 양식의 (   ) 5개: 신규주식인수, 무담보사채, 조건부지분(SAFE), 창업자주식, 프로젝트
    # 투자형태에 매칭되는 항목에만 O (보통주/우선주→주식인수, CB/BW→무담보사채,
    # SAFE→조건부지분, 프로젝트→프로젝트)
    invest_method_checks = [
        is_stock_type,   # 신규로 발행되는 주식의 인수
        is_cb_bw,        # 무담보전환사채/신주인수권부사채/교환사채
        is_safe,         # 조건부지분인수계약(SAFE)
        False,           # 개인/개인투자조합 3년 이상 보유 창업자 주식
        is_project,      # 프로젝트 투자
    ]

    # ── 비고란 적색 주석 (colAddr=3 빈 셀에 순서대로 삽입) ──
    legal_bigo = [
        "",                          # row2: 자기/제3자
        "[확인 필요: 중소기업 여부]",  # row3: 상호출자
        "",                          # row8: 조합명의
        "",                          # row9: 차입
        "",                          # row10: 별도조건
        "[별도 확인 필요]",            # row12: 프로젝트
    ]
    regulatory_bigo = [
        "",                          # row11: 해외투자
        "",                          # row12
        "",                          # row13
        "",                          # row14: 금지행위 (전체 적색 처리)
        "",                          # row15: 투자기간
        "",                          # row16: 납입금액
        "",                          # row17: 이해상충 (전체 적색 처리)
        "",                          # row18: 투심위
    ]

    # ── 담당자 확인 필요 → 해당 행 전체를 적색으로 표시할 항목 키워드 ──
    # 이 항목들은 행 전체(내용+평가+비고) 적색 표시
    red_full_rows = [
        '제34조 제4항의 후행투자 여부',
        '제34조 제10항에 의한 금지행위 여부',
        '제34조의 2 제1항의 이해상충여부 검토 여부',
        '제61조 제14항의 볼커룰',
    ]

    # ── 투자의무4 비고란 주석 ──
    # 제61조 제1항 제1호 → "별도 확인 필요" 적색 표시
    # (이 항목은 비고란이 이미 텍스트가 있으므로 텍스트 기반 주석으로 처리)

    # ── 텍스트 기반 주석 ──
    red_notes = {
        '(상세하게 발굴경위 기재)': rd.discovery_background or '(확인 필요)',
    }
    # 제61조1항2호(TCB): 양식 비고에 이미 '▪' 글머리가 있으므로 등급 텍스트만 채운다.
    # 미해당이면 "본건 TCB 등급" 줄과 "(NICE평가정보, …)" 줄을 통째로 삭제한다.
    remove_paras = []
    tcb_detail = rd.purpose_tcb_detail or ""
    if purpose_tcb == "적" and tcb_detail:
        # "TI-3 등급(2025.8.28 발급)" → 등급 + 발급일 채움
        m = re.search(r'(TI-\d+)\s*등급.*?\(([\d.]+)\s*발급\)', tcb_detail)
        if m:
            red_notes['본건 TCB　등급: TI-'] = f'본건 TCB 등급: {m.group(1)} 등급'
            red_notes['0000.00.00 발급'] = f'{m.group(2)} 발급'
        else:
            red_notes['본건 TCB　등급: TI-'] = f'본건 TCB 등급: {tcb_detail}'
    else:
        # 미해당: 등급 줄(▪ 포함)과 NICE평가정보 줄을 문단째 삭제
        remove_paras += ['본건 TCB', 'NICE평가정보']
    # 투심위 예정일
    red_notes['년  월 일'] = committee_date

    # ── 제35조1항1·2·3호 비고 셀 맨 밑줄 "▪ 근거" 추가 (별첨2 해당 시) ──
    # anchor = 각 조항 비고 셀의 기존 "투자대상 : ..." 텍스트
    bigo_appends = []
    if purpose_transport == "적" and (rd.purpose_transport_detail or "").strip():
        bigo_appends.append(('투자대상 : 국토교통',
                             '▪ ' + rd.purpose_transport_detail.strip()))
    if purpose_mobility == "적" and (rd.purpose_mobility_detail or "").strip():
        bigo_appends.append(('투자대상 : 혁신성장',
                             '▪ ' + rd.purpose_mobility_detail.strip()))
    if purpose_south == "적" and (rd.purpose_south_detail or "").strip():
        bigo_appends.append(('투자대상 : 남부권',
                             '▪ ' + rd.purpose_south_detail.strip()))

    # ── 별첨2 (표6) 대상기업 정보 치환 ──
    # 양식의 별첨2 placeholder([대표이사]·[설립일] 등)를 deal 회사 정보로 교체한다.
    # 추출 불가 항목(사업자번호·법인번호·설립일·주소·영위사업)은 빈칸으로 둔다.
    # ⚠ 한컴은 별첨2 날짜·번호 셀의 형식을 검증하므로 '(확인 필요)' 같은 비정형
    #   텍스트를 넣으면 문서 열기 시 복구 모드가 떠 정상적으로 열리지 않는다.
    NEED = ""
    a2_estab = _format_estab_date_dot(rd.establishment_date) or NEED
    a2_bizdesc = (rd.business_description or ind_desc or "").strip() or NEED
    a2_corpreg = (getattr(rd, 'corp_reg_number', '') or "").strip() or NEED
    a2_invdate = _clean_paren_date(rd.contract_date or rd.fund_date) or NEED
    a2_amt = inv_amt or NEED
    a2_addr = addr or NEED
    # 별첨2 회사명(㈜AAA)·사업자등록번호(000-00-00000)는 _simple 에서 표1과 함께 치환됨.
    attach2 = {
        '[대표이사]': rep or NEED,
        '[설립일]': a2_estab,
        '[영위사업]': a2_bizdesc,
        '[법인등록번호]': a2_corpreg,
        '[투자일자]': a2_invdate,
        '[투자금액]': a2_amt,
        '[주소]': a2_addr,
        '[거래지점]': NEED,        # 중소기업은행 거래지점 (담당자 확인)
        '[작성일]': _today_korean(),  # 확인서 작성일
    }

    return {
        '_simple': {
            '㈜AAA': short,
            '000-00-00000': biz_id,
            '0000년 00월 00일': (_format_estab_date(estab_str) if rd.establishment_date else ''),
            '한국표준산업분류코드 :': ksic_line,
            '이해관계인 :': f'이해관계인 : {interested}',
            '년  월  일': '2029년  9월  8일',
        },
        '_conditions': {
            # 표2 투자유형/금액/단가/지분율 (순서 기반 - >원< 치환)
            ' - 존속기간 :': f' - 존속기간 : {cd.duration}' if cd.duration else ' - 존속기간 :',
            ' - 상환조건 :': f' - 상환조건 : {cd.redemption_terms}' if cd.redemption_terms else ' - 상환조건 :',
            ' - 전환조건 :': f' - 전환조건 : {cd.conversion_terms}' if cd.conversion_terms else ' - 전환조건 :',
            ' - 기타 :': f' - 기타 : {", ".join(extras)} 등' if extras else ' - 기타 :',
            ' - 위약벌 :': f' - 위약벌 : 투자금의 {cd.penalty_rate}%' if cd.penalty_rate else ' - 위약벌 :',
            ' - 지연배상금 :': f' - 지연배상금 : 실제 지급일까지 연 {cd.delay_rate}%' if cd.delay_rate else ' - 지연배상금 :',
            ' - 주식매수청구권 :': f' - 주식매수청구권 : 투자원금 및 {cd.buyback_rate}%' if cd.buyback_rate else ' - 주식매수청구권 :',
        },
        '_ordered': {
            'OOO': [rep, discoverer, reviewer, post_mgr],
            'OO': [addr],
        },
        # 표2 투자유형/금액/단가/지분율: >원< 과 >%< 순서 치환 (4개씩)
        '_table2_values': {
            # text node 22~24: 첫 번째 행 (투자유형 행)
            # text node 27~29: 합계 행
            'stock_type': stock_type,
            'inv_amt': inv_amt,
            'iss_price': iss_price,
            'ratio': ratio,
        },
        '_table4_states': [startup_state, venture_state, innobiz_state],
        '_table5_yn': table5_yn,
        '_invest_method_checks': invest_method_checks,
        '_bigo_notes': legal_bigo + regulatory_bigo,
        '_red_full_rows': red_full_rows,  # 전체 적색 표시할 행 키워드
        '_red_notes': red_notes,
        '_attach2': attach2,              # 별첨2(표6) 대상기업 정보
        '_ibk_o': (ibk_yn == "적"),       # 제61조1항1호(별첨5) 해당 → 비고 (O)
        '_bigo_appends': bigo_appends,    # 표5 조항 비고 셀 맨 밑줄 ▪ 근거
        '_remove_paras': remove_paras,    # 미해당 시 문단째 삭제할 anchor
    }


# ━━━━━━━━━━━━━━━ 치환 엔진 ━━━━━━━━━━━━━━━

def _apply_replacements(text: str, replacements: dict) -> str:
    """모든 치환 규칙을 적용."""
    simple = replacements.get('_simple', {})
    ordered = replacements.get('_ordered', {})
    conditions = replacements.get('_conditions', {})

    # 1. 단순 치환 (빈 문자열로의 치환도 허용 — 미상 필드는 placeholder를 비운다)
    for old_val, new_val in simple.items():
        if old_val:
            text = text.replace(old_val, _xml_safe(new_val or ''))

    # 1.5. 조건/위약벌 개별 태그 치환
    for old_val, new_val in conditions.items():
        if old_val and new_val:
            text = text.replace(old_val, _xml_safe(new_val))

    # 2. 순서 기반 치환 (XML과 PrvText 모두)
    for placeholder, values in ordered.items():
        for new_val in values:
            if new_val:
                safe_val = _xml_safe(new_val)
                # XML: >OOO<
                pat = '>' + re.escape(placeholder) + '<'
                repl = '>' + safe_val + '<'
                text = re.sub(pat, repl, text, count=1)
                # PrvText: <OOO>
                pat2 = '<' + re.escape(placeholder) + '>'
                repl2 = '<' + safe_val + '>'
                text = re.sub(pat2, repl2, text, count=1)

    # 2.5 미치환 OOO/OO 잔재 비우기 (대표·주소 등 미상 시 placeholder가 남으면
    #     한컴이 해당 셀을 비정형으로 인식하므로 빈 셀로 정리한다)
    for ph in ('OOO', 'OO'):
        text = text.replace('>' + ph + '<', '><')   # section0.xml
        text = text.replace('<' + ph + '>', '<>')   # PrvText.txt

    # 3. 표2 투자유형/금액/단가/지분율 치환
    t2 = replacements.get('_table2_values', {})
    if t2.get('stock_type'):
        # 구분 컬럼 첫 번째 빈 셀 (text node 16 다음의 빈 셀)에 투자유형 삽입
        # 양식에서 구분 행 >원< 앞에 빈 셀이 있음. >< 패턴으로 치환은 어려우므로
        # >원< 자체를 값+원 으로 치환 (순서: 투자금액, 투자단가, 합계금액, 합계단가)
        pass

    if t2.get('inv_amt'):
        # 첫 번째 >원< → 투자금액
        text = re.sub(r'>원<', '>' + _xml_safe(t2['inv_amt']) + '<', text, count=1)
    if t2.get('iss_price'):
        # 두 번째 >원< → 투자단가
        text = re.sub(r'>원<', '>' + _xml_safe(t2['iss_price']) + '<', text, count=1)
    if t2.get('ratio'):
        # 첫 번째 >%< → 지분율
        text = re.sub(r'>%<', '>' + _xml_safe(t2['ratio']) + '<', text, count=1)
    if t2.get('stock_type'):
        # 기타(    ) 앞의 빈 셀에 투자유형 삽입은 어려우므로
        # "기타(    )" 를 투자유형으로 치환
        text = text.replace('기타(    )', _xml_safe(t2['stock_type']), 1)

    # 합계 행: 나머지 >원< 과 >%< 치환 (합계 = 같은 값)
    if t2.get('inv_amt'):
        text = re.sub(r'>원<', '>' + _xml_safe(t2['inv_amt']) + '<', text, count=1)
    if t2.get('iss_price'):
        text = re.sub(r'>원<', '>' + _xml_safe(t2['iss_price']) + '<', text, count=1)
    if t2.get('ratio'):
        text = re.sub(r'>%<', '>' + _xml_safe(t2['ratio']) + '<', text, count=1)

    # 4. 표4 검토결과(창업/벤처/이노비즈) — 셀 단위로 적(Y)/부(N) 중 하나만, 미확정은 공란
    # 표4 영역의 "적(Y)·부(N)이 함께 든 셀" 3개를 순서대로(창업·벤처·이노비즈) 채운다.
    # (전역 치환은 앞 행 선택값을 뒷 행이 지우는 문제가 있어 셀 단위로 처리)
    table4_states = replacements.get('_table4_states', [])
    if table4_states:
        s4 = text.find("4. 투자기업의 벤처기업")
        e4 = text.find("5. 준법사항", s4) if s4 >= 0 else -1
        if s4 >= 0 and e4 >= 0:
            region = text[s4:e4]
            out, last, idx = [], 0, 0
            for m in re.finditer(r'<hp:tc\b.*?</hp:tc>', region, re.DOTALL):
                cell = m.group(0)
                if ('<hp:t>적(Y)</hp:t>' in cell and '<hp:t>부(N)</hp:t>' in cell
                        and idx < len(table4_states)):
                    st = table4_states[idx]
                    idx += 1
                    if st == "Y":
                        cell = re.sub(r'charPrIDRef="\d+"(><hp:t>적\(Y\)</hp:t>)',
                                      f'charPrIDRef="{RED_CHARPR_ID}"\\1', cell, count=1)
                        cell = cell.replace('<hp:t>부(N)</hp:t>', '<hp:t></hp:t>', 1)
                    elif st == "N":
                        cell = re.sub(r'charPrIDRef="\d+"(><hp:t>부\(N\)</hp:t>)',
                                      f'charPrIDRef="{RED_CHARPR_ID}"\\1', cell, count=1)
                        cell = cell.replace('<hp:t>적(Y)</hp:t>', '<hp:t></hp:t>', 1)
                    else:  # 공란
                        cell = cell.replace('<hp:t>적(Y)</hp:t>', '<hp:t></hp:t>', 1)
                        cell = cell.replace('<hp:t>부(N)</hp:t>', '<hp:t></hp:t>', 1)
                out.append(region[last:m.start()])
                out.append(cell)
                last = m.end()
            region = ''.join(out) + region[last:]
            text = text[:s4] + region + text[e4:]

    # 4.5 투자방법 (O) 체크 - "(   )" 를 "(O)" 또는 유지
    method_checks = replacements.get('_invest_method_checks', [])
    for i, checked in enumerate(method_checks):
        if checked:
            text = text.replace('(   )', '(O)', 1)
        else:
            # 체크 안된 항목도 한번 건너뜀 (순서 유지)
            idx = text.find('(   )')
            if idx >= 0:
                pass  # 그대로 유지
            # 다음 (   )로 이동하기 위해 임시 마킹 후 복원
            text = text.replace('(   )', '(___SKIP___)', 1)
    # 복원
    text = text.replace('(___SKIP___)', '(   )')

    # 5. 표5 실제 칼럼 빈 셀에 적/부 값 채우기
    table5_yn = replacements.get('_table5_yn', [])
    if table5_yn:
        t5_start = text.find('5. 준법사항 확인')
        if t5_start >= 0:
            before = text[:t5_start]
            after = text[t5_start:]

            # tc 단위로 분리하여 colAddr="2"인 빈 셀만 찾기
            tc_pattern = re.compile(r'(<hp:tc\b[^>]*>)(.*?)(</hp:tc>)', re.DOTALL)
            yn_idx = 0

            def _fill_cell(m):
                nonlocal yn_idx
                tc_open = m.group(1)
                tc_body = m.group(2)
                tc_close = m.group(3)

                # colAddr="2" 이고 빈 셀 (자체닫기 run)인 경우만
                if 'colAddr="2"' not in tc_body:
                    return m.group(0)
                row_m = re.search(r'rowAddr="(\d+)"', tc_body)
                row = int(row_m.group(1)) if row_m else -1
                if row < 2:
                    return m.group(0)

                # 자체닫기 run이 있는지 확인
                empty_run = re.search(r'<hp:run charPrIDRef="(\d+)"/>', tc_body)
                if not empty_run:
                    return m.group(0)

                # 이미 <hp:t>가 있으면 건너뜀
                if '<hp:t>' in tc_body:
                    return m.group(0)

                if yn_idx >= len(table5_yn):
                    return m.group(0)

                val = table5_yn[yn_idx]
                yn_idx += 1

                old_run = f'<hp:run charPrIDRef="{empty_run.group(1)}"/>'
                new_run = f'<hp:run charPrIDRef="{empty_run.group(1)}"><hp:t>{val}</hp:t></hp:run>'
                tc_body = tc_body.replace(old_run, new_run, 1)

                return tc_open + tc_body + tc_close

            after = tc_pattern.sub(_fill_cell, after)
            text = before + after

    # 6. 비고란(colAddr=3) 빈 셀에 적색 주석 채우기
    bigo_notes = replacements.get('_bigo_notes', [])
    if bigo_notes:
        t5_start = text.find('5. 준법사항 확인')
        if t5_start >= 0:
            before5 = text[:t5_start]
            after5 = text[t5_start:]

            tc_pattern = re.compile(r'(<hp:tc\b[^>]*>)(.*?)(</hp:tc>)', re.DOTALL)
            bigo_idx = 0

            def _fill_bigo(m):
                nonlocal bigo_idx
                tc_open = m.group(1)
                tc_body = m.group(2)
                tc_close = m.group(3)

                if 'colAddr="3"' not in tc_body:
                    return m.group(0)
                row_m = re.search(r'rowAddr="(\d+)"', tc_body)
                row = int(row_m.group(1)) if row_m else -1
                if row < 2:
                    return m.group(0)

                empty_run = re.search(r'<hp:run charPrIDRef="(\d+)"/>', tc_body)
                if not empty_run:
                    return m.group(0)
                if '<hp:t>' in tc_body:
                    return m.group(0)

                if bigo_idx >= len(bigo_notes):
                    return m.group(0)

                note = bigo_notes[bigo_idx]
                bigo_idx += 1

                if note:
                    safe_note = _xml_safe(note)
                    old_run = f'<hp:run charPrIDRef="{empty_run.group(1)}"/>'
                    # 적색+기울임 charPr(id=156) 사용
                    new_run = f'<hp:run charPrIDRef="{RED_ITALIC_CHARPR_ID}"><hp:t>{safe_note}</hp:t></hp:run>'
                    tc_body = tc_body.replace(old_run, new_run, 1)

                return tc_open + tc_body + tc_close

            after5 = tc_pattern.sub(_fill_bigo, after5)
            text = before5 + after5

    # 7. 담당자 확인 필요 행 → 행 전체를 적색(157)으로 변경
    # 역순으로 처리하여 앞쪽 위치에 영향 주지 않음
    red_full_rows = replacements.get('_red_full_rows', [])
    # 키워드 위치로 정렬 후 역순 처리
    red_positions = []
    for keyword in red_full_rows:
        idx = text.find(keyword)
        if idx >= 0:
            red_positions.append((idx, keyword))
    red_positions.sort(reverse=True)  # 뒤에서부터 처리

    for idx, keyword in red_positions:
        tr_start = text.rfind('<hp:tr', 0, idx)
        tr_end = text.find('</hp:tr>', idx)
        if tr_start >= 0 and tr_end >= 0:
            tr_end += len('</hp:tr>')
            tr_chunk = text[tr_start:tr_end]
            modified_tr = re.sub(r'charPrIDRef="\d+"', f'charPrIDRef="{RED_CHARPR_ID}"', tr_chunk)
            text = text[:tr_start] + modified_tr + text[tr_end:]

    # 8. 텍스트 기반 주석 (발굴경위, TCB등급, 투심위예정일)
    red_notes = replacements.get('_red_notes', {})
    for keyword, note in red_notes.items():
        if keyword in text:
            safe_note = _xml_safe(note)
            # keyword를 note로 완전 교체 (중복 방지)
            text = text.replace(keyword, safe_note, 1)

    # 8.5 표5 조항 비고 셀 — 별첨2/별첨5 근거 반영
    # 제61조1항1호: 별첨5 해당 시 비고 "투자대상 : 중소기업은행 …" 끝에 (O)
    #   (확인서 제목 등 다른 occurrence 보호 위해 표5 비고 셀 텍스트만 단건 치환)
    if replacements.get('_ibk_o'):
        text = text.replace(
            '투자대상 : 중소기업은행 신규 및 기존거래 기업',
            '투자대상 : 중소기업은행 신규 및 기존거래 기업 (O)', 1)
    # 제35조1항1·2·3호: 해당 조항 비고 셀 맨 밑줄에 "▪ 근거" 문단 추가
    for anchor, bullet in replacements.get('_bigo_appends', []):
        text = _inject_bigo_append(text, anchor, bullet)

    # 8.6 미해당 항목의 placeholder 문단 삭제 (예: TCB 미해당 시 등급/NICE 줄)
    for anchor in replacements.get('_remove_paras', []):
        a = text.find(anchor)
        if a < 0:
            continue
        ps = text.rfind('<hp:p ', 0, a)
        pe = text.find('</hp:p>', a)
        if ps >= 0 and pe >= 0:
            text = text[:ps] + text[pe + len('</hp:p>'):]

    # 8.7 제35조3호(남부권)·투자비율점검 투자의무3 → 양식의 적색 글자를 흑색으로
    #     (해당여부 무관). 적색 charPr 가 다른 항목과 공유되므로 흑색 트윈으로 재지정.
    twins = replacements.get('_black_twins', {})
    if twins:
        red_set = set(twins)
        # (a) 표5 제35조3호 행: 행 내 적색 run 전부 흑색 (검토결과 적/부=157은 트윈 제외라 유지)
        ki = text.find('제35조 제1항 제3호의 투자 해당여부')
        if ki >= 0:
            ts = text.rfind('<hp:tr', 0, ki)
            te = text.find('</hp:tr>', ki)
            if ts >= 0 and te >= 0:
                te += len('</hp:tr>')
                chunk = text[ts:te]
                for r, b in twins.items():
                    chunk = chunk.replace('charPrIDRef="%s"' % r, 'charPrIDRef="%s"' % b)
                text = text[:ts] + chunk + text[te:]
        # (b) 남부권/투자의무3 관련 개별 run(투자비율점검 표 포함)을 흑색으로
        _kws = ('투자의무3', '남부권', '동남권', '서남권', '10,000백만원')

        def _blk(m):
            cid, attrs, body = m.group(1), m.group(2), m.group(3)
            if cid not in red_set:
                return m.group(0)
            t = re.sub(r'<[^>]+>', '', ''.join(re.findall(r'<hp:t>(.*?)</hp:t>', body, re.DOTALL)))
            if any(k in t for k in _kws):
                return '<hp:run charPrIDRef="%s"%s>%s</hp:run>' % (twins[cid], attrs, body)
            return m.group(0)

        text = re.sub(r'<hp:run charPrIDRef="(\d+)"([^>]*)>(.*?)</hp:run>', _blk, text, flags=re.DOTALL)

    # 9. 별첨2(표6) 대상기업 정보 치환 + 담당자확인 셀 비우기
    #    양식의 별첨2 placeholder를 deal 회사 정보로 교체. 인정여부(여신/외환/수신
    #    Y/N)·증빙서류 셀은 담당자 확인 항목이므로 비워 둔다.
    attach2 = replacements.get('_attach2', {})
    if attach2:
        anchor = text.find('중소기업은행 신규 및 기존거래 기업 인정 확인서')
        if anchor >= 0:
            head = text[:anchor]
            tail = text[anchor:]
            for old_val, new_val in attach2.items():
                if old_val:
                    tail = tail.replace(old_val, _xml_safe(new_val or ""), 1)
            # 인정여부 Y/N·증빙서류 O 비우기 (별첨2 영역 한정)
            for token in ('<hp:t>Y</hp:t>', '<hp:t>N</hp:t>', '<hp:t>O</hp:t>'):
                tail = tail.replace(token, '<hp:t></hp:t>')
            text = head + tail

    return text


def _inject_bigo_append(text: str, anchor: str, bullet: str) -> str:
    """anchor 텍스트를 포함한 표5 비고 셀(<hp:tc>)의 맨 밑줄에 새 문단(▪ 근거)을 추가.

    셀 내 첫 문단(<hp:p>, anchor 보유)을 복제해 paraPr/charPr/run 구조를 그대로
    물려받고, lineSeg 레이아웃 캐시는 제거(한컴이 열 때 재계산 → 복구모드 방지)한
    뒤 텍스트를 bullet 로 교체하여 마지막 문단 뒤에 삽입한다. 멱등(이미 동일 bullet
    이 있으면 재삽입하지 않음)."""
    a = text.find(anchor)
    if a < 0:
        return text
    tc_start = text.rfind('<hp:tc', 0, a)
    tc_end = text.find('</hp:tc>', a)
    if tc_start < 0 or tc_end < 0:
        return text
    tc_end += len('</hp:tc>')
    tc = text[tc_start:tc_end]

    safe = _xml_safe(bullet)
    if f'<hp:t>{safe}</hp:t>' in tc:   # 멱등
        return text

    paras = list(re.finditer(r'<hp:p\b.*?</hp:p>', tc, re.DOTALL))
    if not paras:
        return text
    template_p = paras[0].group(0)
    # lineSeg 캐시 제거 (한컴 재계산)
    new_p = re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', template_p, flags=re.DOTALL)
    # 첫 <hp:t> 만 bullet 로, 나머지 run 텍스트는 비움
    done = {'v': False}

    def _set_t(m):
        if not done['v']:
            done['v'] = True
            return '<hp:t>' + safe + '</hp:t>'
        return '<hp:t></hp:t>'

    new_p = re.sub(r'<hp:t>.*?</hp:t>', _set_t, new_p, flags=re.DOTALL)
    if not done['v']:
        return text   # 텍스트 노드가 없으면 포기

    last_end = paras[-1].end()
    new_tc = tc[:last_end] + new_p + tc[last_end:]
    return text[:tc_start] + new_tc + text[tc_end:]


def _fix_overshoot_linesegs(section_xml: str) -> str:
    """치환 후 각 문단의 <hp:lineseg> 레이아웃 캐시를 실제 텍스트 길이에 맞춘다.

    HWPX 문단은 <hp:linesegarray> 안에 줄바꿈 위치를 캐시한다(<hp:lineseg textpos="N">).
    양식의 긴 placeholder를 짧은 값으로 치환하면 두 번째 이후 lineseg 의 textpos 가
    실제 텍스트 길이를 초과하게 되고, 한컴이 이 불일치를 감지해 문서를 '복구' 모드로만
    연다(=정상 열림 실패, 사용자에겐 복구 대화상자). textpos 가 텍스트 길이를 넘는
    lineseg 를 제거해 일관성을 회복한다(첫 lineseg textpos=0 은 항상 보존).
    """
    def _fix_para(m):
        para = m.group(0)
        if '<hp:lineseg' not in para:
            return para
        tlen = sum(len(t) for t in re.findall(r'<hp:t>(.*?)</hp:t>', para, re.DOTALL))

        def _keep(seg):
            tp = int(seg.group(1))
            return seg.group(0) if tp <= tlen else ''

        return re.sub(r'<hp:lineseg textpos="(\d+)"[^>]*/>', _keep, para)

    return re.sub(r'<hp:p\b.*?</hp:p>', _fix_para, section_xml, flags=re.DOTALL)


def _copy_and_replace(template_path: str, output_path: str, replacements: dict):
    """양식 HWPX를 복사하고 치환. flag_bits 등 원본 메타데이터 완전 보존."""
    import struct
    import shutil

    temp_path = output_path + '.tmp'

    with zipfile.ZipFile(template_path, 'r') as zin:
        modified = {}

        # 검정 트윈 charPr 준비: 양식 원래 적색 charPr(156/157 제외)의 흑색 사본을 만들어
        # 제35조3호·투자의무3(남부권) 글자만 흑색으로 재지정하기 위함. (트윈맵을 치환에 전달)
        header = zin.read('Contents/header.xml').decode('utf-8', errors='replace')
        red_ids = [i for i in re.findall(r'<hh:charPr\s+id="(\d+)"[^>]*textColor="#FF0000"', header)
                   if i not in (RED_ITALIC_CHARPR_ID, RED_CHARPR_ID)]
        header, twin_map = _add_black_twins(header, red_ids)
        replacements['_black_twins'] = twin_map
        header = _add_red_italic_charpr(header)
        modified['Contents/header.xml'] = header.encode('utf-8')

        # section0.xml, PrvText.txt 치환
        for fname in ('Contents/section0.xml', 'Preview/PrvText.txt'):
            text = zin.read(fname).decode('utf-8', errors='replace')
            text = _apply_replacements(text, replacements)
            if fname == 'Contents/section0.xml':
                # 치환으로 텍스트가 짧아진 문단의 lineSeg 레이아웃 캐시를 정리.
                # (캐시가 실제 텍스트보다 길면 한컴이 '복구' 모드로만 열린다)
                text = _fix_overshoot_linesegs(text)
            modified[fname] = text.encode('utf-8')

        with zipfile.ZipFile(temp_path, 'w') as zout:
            for item in zin.infolist():
                if item.filename in modified:
                    data = modified[item.filename]
                else:
                    data = zin.read(item.filename)
                zout.writestr(item, data)

    # flag_bits 복원: ZIP 바이너리에서 직접 패치
    _patch_flag_bits(template_path, temp_path)
    os.replace(temp_path, output_path)


def _patch_flag_bits(template_path: str, target_path: str):
    """원본 HWPX의 flag_bits를 생성본에 복사. (local + central directory 모두)"""
    import struct

    with zipfile.ZipFile(template_path) as zt:
        orig_flags = {item.filename: item.flag_bits for item in zt.infolist()}

    # ZIP 파일 바이너리 읽기
    with open(target_path, 'rb') as f:
        data = bytearray(f.read())

    # Local file headers: signature = PK\x03\x04
    offset = 0
    while offset < len(data) - 4:
        sig = struct.unpack_from('<I', data, offset)[0]
        if sig == 0x04034b50:  # Local file header
            fname_len = struct.unpack_from('<H', data, offset + 26)[0]
            extra_len = struct.unpack_from('<H', data, offset + 28)[0]
            fname = data[offset + 30: offset + 30 + fname_len].decode('utf-8', errors='replace')
            if fname in orig_flags:
                struct.pack_into('<H', data, offset + 6, orig_flags[fname])
            comp_size = struct.unpack_from('<I', data, offset + 18)[0]
            offset += 30 + fname_len + extra_len + comp_size
        elif sig == 0x02014b50:  # Central directory header
            fname_len = struct.unpack_from('<H', data, offset + 28)[0]
            extra_len = struct.unpack_from('<H', data, offset + 30)[0]
            comment_len = struct.unpack_from('<H', data, offset + 32)[0]
            fname = data[offset + 46: offset + 46 + fname_len].decode('utf-8', errors='replace')
            if fname in orig_flags:
                struct.pack_into('<H', data, offset + 8, orig_flags[fname])
            offset += 46 + fname_len + extra_len + comment_len
        elif sig == 0x06054b50:  # End of central directory
            break
        else:
            offset += 1

    with open(target_path, 'wb') as f:
        f.write(data)


# ━━━━━━━━━━━━━━━ 유틸 ━━━━━━━━━━━━━━━

RED_ITALIC_CHARPR_ID = "156"  # 적색+기울임 (주석용)
RED_CHARPR_ID = "157"         # 적색만 (행 전체 강조용)


def _add_red_italic_charpr(header_xml: str) -> str:
    """header.xml에 적색+기울임(156)과 적색만(157) charPr을 추가."""
    import re
    m = re.search(r'(<hh:charPr\s+id="22".*?</hh:charPr>)', header_xml, re.DOTALL)
    if not m:
        return header_xml

    base = m.group(1)
    new_entries = ""
    added = 0

    # charPr 156: 적색 + 기울임 (주석용)
    if f'id="{RED_ITALIC_CHARPR_ID}"' not in header_xml:
        cp156 = base.replace('id="22"', f'id="{RED_ITALIC_CHARPR_ID}"')
        cp156 = cp156.replace('textColor="#000000"', 'textColor="#FF0000"')
        cp156 = cp156.replace('useFontSpace=', 'italic="1" useFontSpace=')
        new_entries += cp156 + "\n"
        added += 1

    # charPr 157: 적색만 (행 전체 강조용)
    if f'id="{RED_CHARPR_ID}"' not in header_xml:
        cp157 = base.replace('id="22"', f'id="{RED_CHARPR_ID}"')
        cp157 = cp157.replace('textColor="#000000"', 'textColor="#FF0000"')
        new_entries += cp157 + "\n"
        added += 1

    if new_entries:
        header_xml = header_xml.replace('</hh:charProperties>', new_entries + '</hh:charProperties>')
        # ⚠ 중요: charProperties itemCnt 를 추가한 개수만큼 증가시켜야 한다.
        # itemCnt 가 실제 charPr 수보다 작으면 한컴이 초과분(156/157)을 무시하여
        # docx 변환 시 적색 서식이 사라진다.
        def _bump(mm):
            return f'{mm.group(1)}{int(mm.group(2)) + added}{mm.group(3)}'
        header_xml = re.sub(
            r'(<hh:charProperties\b[^>]*\bitemCnt=")(\d+)(")',
            _bump, header_xml, count=1,
        )
    return header_xml


def _add_black_twins(header_xml: str, red_ids):
    """양식의 적색 charPr 들의 흑색 사본(트윈)을 header 에 추가하고 {적색id: 흑색id} 반환.
    공유 charPr(투자의무3 ↔ 투자의무1/4 등) 때문에, 특정 글자만 흑색화할 때 사용."""
    twin = {}
    additions = []
    for rid in dict.fromkeys(red_ids):  # 중복 제거, 순서 유지
        m = re.search(r'<hh:charPr\s+id="%s"[\s>].*?</hh:charPr>' % re.escape(rid),
                      header_xml, re.DOTALL)
        if not m:
            m = re.search(r'<hh:charPr\s+id="%s"[\s>][^>]*/>' % re.escape(rid), header_xml)
        if not m:
            continue
        nid = str(int(rid) + 400)
        while ('id="%s"' % nid) in header_xml or any(('id="%s"' % nid) in a for a in additions):
            nid = str(int(nid) + 400)
        block = re.sub(r'\bid="%s"' % re.escape(rid), 'id="%s"' % nid, m.group(0), count=1)
        block = block.replace('textColor="#FF0000"', 'textColor="#000000"')
        additions.append(block)
        twin[rid] = nid
    if additions:
        header_xml = header_xml.replace(
            '</hh:charProperties>', '\n'.join(additions) + '</hh:charProperties>', 1)

        def _bump(mm):
            return '%s%d%s' % (mm.group(1), int(mm.group(2)) + len(additions), mm.group(3))
        header_xml = re.sub(r'(<hh:charProperties\b[^>]*\bitemCnt=")(\d+)(")',
                            _bump, header_xml, count=1)
    return header_xml, twin


def _xml_safe(text: str) -> str:
    """XML 특수문자를 이스케이프한다. 이미 이스케이프된 것은 건너뜀."""
    if not text:
        return text
    # 이미 이스케이프된 &amp; 등은 보존
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', text)
    # < > 는 XML 태그가 아닌 경우만 (PrvText에서는 구분자로 사용)
    # section0.xml에서는 이미 태그 안이므로 < > 치환 불필요
    return text


def _fmt_won(val: str) -> str:
    if not val:
        return ""
    v = val.replace(',', '').replace('원', '').strip()
    if v:
        return f"{int(v):,}원"
    return val


def _check_startup(establishment_date: str) -> str:
    """설립일 기준 7년 이내인지 확인."""
    if not establishment_date:
        return "부(N)"
    try:
        # "2017.05.25" or "2017년 5월 25일" 등
        cleaned = re.sub(r'[년월일\s]', '.', establishment_date).strip('.')
        parts = [p for p in cleaned.split('.') if p]
        if len(parts) >= 1:
            year = int(parts[0])
            current_year = datetime.now().year
            if current_year - year <= 7:
                return "적(Y)"
    except (ValueError, IndexError):
        pass
    return "부(N)"


def _format_estab_date(estab: str) -> str:
    """설립일을 "YYYY년 MM월 DD일" 형태로 변환."""
    if not estab or estab == "0000년 00월 00일":
        return "0000년 00월 00일"
    cleaned = re.sub(r'[년월일\s]', '.', estab).strip('.')
    parts = [p for p in cleaned.split('.') if p]
    if len(parts) >= 3:
        return f"{parts[0]}년 {parts[1]}월 {parts[2]}일"
    elif len(parts) == 2:
        return f"{parts[0]}년 {parts[1]}월"
    return estab


def _format_estab_date_dot(estab: str) -> str:
    """설립일을 별첨2 양식 형태 'YYYY.MM.DD' 로 변환. 값이 없으면 빈 문자열."""
    if not estab or estab == "0000년 00월 00일":
        return ""
    cleaned = re.sub(r'[년월일\s]', '.', estab).strip('.')
    parts = [p for p in cleaned.split('.') if p]
    if len(parts) >= 3:
        return f"{int(parts[0]):04d}.{int(parts[1]):02d}.{int(parts[2]):02d}"
    return estab


def _clean_paren_date(val: str) -> str:
    """'2025.12.24 (예정)' → '2025.12.24'. 괄호 주석·공백 제거."""
    if not val:
        return ""
    v = re.sub(r'\(.*?\)', '', val).strip()
    return v


def _today_korean() -> str:
    """오늘 날짜를 'YYYY년 M월 D일' 형태로."""
    t = date.today()
    return f"{t.year}년 {t.month}월 {t.day}일"


def _yn(val: str) -> str:
    """'해당'/'미해당' 등을 '적'/'부'로 변환."""
    if not val:
        return "부"
    v = val.strip()
    if v in ('해당', '가능', '적합', 'Y', 'O', '있음'):
        return "적"
    return "부"


def _is_before_deadline() -> bool:
    """현재 날짜가 투자기간 종료일(2029.9.8) 이전인지."""
    return date.today() < date(2029, 9, 8)


def _check_mismatches(cd, rd) -> list:
    warnings = []
    def _norm(v):
        return re.sub(r'[\s,원주%㈜주식회사(주)]', '', str(v or ''))
    checks = [
        ("투자금액", rd.investment_amount, _fmt_won(cd.total_investment)),
        ("투자단가", rd.issue_price, _fmt_won(cd.issue_price)),
        ("투자방식", rd.stock_type, cd.stock_type),
    ]
    for name, rv, cv in checks:
        if rv and cv and _norm(rv) != _norm(cv):
            warnings.append(f"{name}: 투심보고서={rv}, 투자계약서={cv}")
            print(f"[WARNING] {name} 불일치: 투심보고서={rv}, 투자계약서={cv}")
    return warnings
