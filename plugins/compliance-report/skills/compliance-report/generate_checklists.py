#!/usr/bin/env python3
"""
준법사항체크리스트(준법감시보고서) 자동 생성 시스템

투자계약서와 투자심사보고서를 입력받아 다음 문서를 자동 생성합니다:
- 준법사항체크리스트 (.hwpx) — 준법감시보고서 정본

사용법:
  python generate_checklists.py \\
    --contract "투자계약서.docx" \\
    --report "투심보고서.docx" \\
    --output-dir ./output

※ 투자계약서 체크리스트(.docx) 만 단독으로 필요하면 별도 스킬을 사용하세요:
  https://github.com/antonio103first/investment-contract-checklist
"""
import argparse
import json
import os
import sys

from extractors.contract_extractor import extract_contract_data
from extractors.report_extractor import extract_report_data
from generators.hwpx_generator import generate_hwpx_checklist


# 수동 확정 주입 가능한 회사정보 필드 (report_data 속성명)
_OVERRIDE_FIELDS = (
    "company_name", "representative", "address", "establishment_date",
    "business_registration", "corp_reg_number", "industry_code",
    "business_description", "contract_date",
)


def _apply_overrides(args, contract_data, report_data):
    """--company-name / --company-data(JSON) / --enrich 로 확정 정보를 주입한다.

    준법문서 임의주입 금지 규칙: 추출 실패값을 추측하지 않고, 사용자가 확정한
    값(또는 확정 사업자번호 기준 bizno 조회값)만 주입한다.
    """
    # 1) --company-name (회사명 직접 지정)
    if args.company_name:
        report_data.company_name = args.company_name
        if not contract_data.company_name:
            contract_data.company_name = args.company_name
        print(f"  [수동] 회사명 지정: {args.company_name}")

    # 2) --company-data (확정 JSON 주입)
    data = {}
    if args.company_data:
        if not os.path.exists(args.company_data):
            print(f"[ERROR] company-data 파일을 찾을 수 없습니다: {args.company_data}")
            sys.exit(1)
        with open(args.company_data, encoding="utf-8") as f:
            data = json.load(f)

    # 3) --enrich (확정 사업자번호 → bizno 조회로 빈 값 보완)
    if args.enrich:
        biz_no = data.get("business_registration") or report_data.business_registration
        if not biz_no:
            print("  [enrich] 사업자번호가 없어 bizno 조회를 건너뜁니다.")
        else:
            try:
                from extractors.bizno_enricher import lookup as bizno_lookup
                fetched = bizno_lookup(biz_no) or {}
                # JSON 에 명시된 값이 우선, 비어있는 칸만 bizno 로 채움
                for k, v in fetched.items():
                    if v and not data.get(k):
                        data[k] = v
                        print(f"  [enrich] bizno → {k}: {v}")
            except Exception as e:  # noqa: BLE001
                print(f"  [enrich] bizno 조회 실패: {e}")

    # 4) 확정 데이터를 report_data 에 주입 (빈 값은 건드리지 않음)
    for k in _OVERRIDE_FIELDS:
        v = data.get(k)
        if v:
            setattr(report_data, k, v)
            print(f"  [확정] {k}: {v}")


def main():
    parser = argparse.ArgumentParser(
        description="준법사항체크리스트(준법감시보고서) 자동 생성 시스템"
    )
    parser.add_argument(
        "--contract", required=True,
        help="투자계약서 파일 경로 (.docx 또는 .pdf)"
    )
    parser.add_argument(
        "--report", required=True,
        help="투자심사보고서 파일 경로 (.docx 또는 .pdf)"
    )
    parser.add_argument(
        "--output-dir", default="./output",
        help="출력 디렉토리 (기본: ./output)"
    )
    parser.add_argument(
        "--company-name", default=None,
        help="회사명 수동 지정 (계약서·투심보고서에서 추출 실패 시, 예: ㈜AAA)"
    )
    parser.add_argument(
        "--company-data", default=None,
        help="확정 회사정보 JSON 파일 경로. 사업자번호·설립일·주소·법인번호·KSIC 등 "
             "문서에 없는 값을 수동 확정 주입 (준법문서 임의주입 금지 규칙 준수)"
    )
    parser.add_argument(
        "--enrich", action="store_true",
        help="--company-data 에 business_registration 이 있으면 bizno.net 조회로 "
             "비어있는 설립일·주소·KSIC 등을 보완 (확정 사업자번호 기준)"
    )
    args = parser.parse_args()

    # 파일 존재 확인
    for path, name in [(args.contract, "투자계약서"), (args.report, "투심보고서")]:
        if not os.path.exists(path):
            print(f"[ERROR] {name} 파일을 찾을 수 없습니다: {path}")
            sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # 1단계: 투자계약서 데이터 추출
    print("=" * 60)
    print("[1/3] 투자계약서 데이터 추출 중...")
    contract_data = extract_contract_data(args.contract)
    print(f"  회사명: {contract_data.company_name}")
    print(f"  투자금액: {contract_data.total_investment}원")
    print(f"  투자단가: {contract_data.issue_price}원")
    print(f"  발행주식수: {contract_data.total_shares}주")
    print(f"  투자방식: {contract_data.stock_type}")
    print(f"  조문 - 투자금용도: 제{contract_data.article_fund_usage}조")
    print(f"  조문 - 주식매수청구권: 제{contract_data.article_buyback}조")
    print(f"  조문 - 손해배상/위약벌: 제{contract_data.article_damages}조")
    print(f"  조문 - 지연배상금: 제{contract_data.article_delay_penalty}조")

    # 2단계: 투심보고서 데이터 추출
    print()
    print("[2/3] 투자심사보고서 데이터 추출 중...")
    report_data = extract_report_data(args.report)

    # 2-1단계: 수동 확정 정보 주입 (--company-name / --company-data / --enrich)
    _apply_overrides(args, contract_data, report_data)

    print(f"  회사명: {report_data.company_name}")
    print(f"  대표이사: {report_data.representative}")
    print(f"  사업자번호: {report_data.business_registration}")
    print(f"  지분율: {report_data.share_ratio}")
    print(f"  펀드명: {report_data.fund_name}")
    print(f"  발굴자: {report_data.discoverer}")
    print(f"  심사자: {report_data.reviewer}")

    # 회사명으로 출력 파일명 구성
    company_short = report_data.company_name or contract_data.company_name
    company_short = company_short.replace('㈜', '').replace('주식회사', '').replace('(주)', '').strip()

    # 3단계: 준법감시보고서(준법사항체크리스트) 생성
    print()
    print("[3/3] 준법감시보고서(준법사항체크리스트) 생성 중...")
    fund_short = report_data.fund_name or "펀드"
    hwpx_output = os.path.join(
        args.output_dir,
        f"준법사항체크리스트_{fund_short}_{company_short}.hwpx"
    )
    generate_hwpx_checklist(contract_data, report_data, hwpx_output)

    # 완료 요약
    print()
    print("=" * 60)
    print("생성 완료!")
    print(f"  준법사항체크리스트(HWPX): {hwpx_output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
