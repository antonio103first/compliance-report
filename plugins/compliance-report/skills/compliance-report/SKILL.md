---
name: compliance-report
description: >-
  준법감시보고서 작성 — K-Run Ventures 케이런7호(2024 IBK혁신 케이런 모빌리티 7호) 펀드 투자건의
  투자계약서와 투자심사보고서로부터 「준법사항체크리스트(준법감시보고서)」 한글(.hwpx) 문서를
  자동 생성한다. 다음 상황에서 사용: 투자계약서·투자심사보고서(docx/hwp/pdf)를 제시하며
  "준법감시보고서 작성", "준법사항체크리스트 작성", "체크리스트 만들어줘"를 요청할 때,
  또는 투자건의 준법사항 검토가 필요할 때.
---

# 준법감시보고서 작성

투자계약서와 투자심사보고서를 입력받아, **투자계약 전 준법감시인이 작성해야 하는
준법사항체크리스트(준법감시보고서) 정본**을 한글 `.hwpx` 로 자동 생성하는 스킬이다.

생성된 hwpx 는 한컴오피스에서 **복구 모드 없이 바로 열리며**, 표1~5 + 별첨2(중소기업은행 신규·기존거래
기업 인정 확인서)까지 자동으로 채워진다.

> 🔗 **투자계약서 체크리스트(.docx)** 만 필요하면 별도 스킬을 사용한다:
> [investment-contract-checklist](https://github.com/antonio103first/investment-contract-checklist)

## 입력 형식

| 형식 | 비고 |
|------|------|
| `.docx` (Word) | 투자계약서·투심보고서 — 가장 정확 |
| `.hwp` (한글 v5.0) | 투자계약서 (olefile 기반 텍스트 추출, 표 구조는 제한적) |
| `.pdf` | 텍스트 PDF 직접 추출 / 스캔본은 Tesseract OCR |

> 원본이 `.hwp/.hwpx` 라면 한글에서 **다른 이름으로 저장 → `.docx`** 로 변환 후 사용하면 가장 정확하다.

## 번들 스크립트 경로 (중요)

이 스킬에는 `generate_checklists.py` 와 `extractors/`, `generators/`, 양식 파일이 SKILL.md 와 같은 폴더에 번들되어 있다.
스킬 실행 시 작업 디렉토리는 사용자의 프로젝트 폴더이므로, 스크립트는 **반드시 스킬 폴더의 절대경로**로 실행한다.
양식 파일은 스크립트가 `__file__` 기준으로 자동 탐색하므로 별도 지정이 필요 없다.

- **플러그인으로 설치된 경우**: `${CLAUDE_PLUGIN_ROOT}/skills/compliance-report`
- **standalone(`~/.claude/skills/...`) 설치인 경우**: 이 SKILL.md 가 위치한 폴더

아래에서 `<SKILL_DIR>` 은 이 SKILL.md 가 있는 폴더의 절대경로로 치환한다.

## 작업 절차

### 1단계 — 입력 파일 확인

사용자가 제시한 **투자계약서**와 **투자심사보고서** 파일 경로를 확인한다. 두 파일이 모두 필요하다.

### 2단계 — 생성 실행

```bash
python "<SKILL_DIR>/generate_checklists.py" \
  --contract "투자계약서_OOO.docx" \
  --report   "투심보고서_OOO.docx" \
  --output-dir ./output
```

다음이 생성된다.
- `output/준법사항체크리스트_{펀드}_{회사}.hwpx` — **준법감시보고서 정본**

스크립트가 콘솔에 추출된 핵심값(회사명·대표이사·투자금액·단가·조문번호 등)과 **데이터 불일치 경고**를 출력한다.

### 3단계 — 미상 정보 보완 (선택)

투심보고서·계약서에 **사업자등록번호·설립일·주소·법인등록번호**가 없는 경우가 많다(축약본/마스킹). 이때:

- **회사명이 추출되지 않으면** `--company-name "㈜AAA"` 로 직접 지정한다.
- **확정된 사업자등록번호가 있으면** JSON 파일로 주입하고, `--enrich` 로 bizno.net 에서
  설립일·주소·법인번호·업종을 보완한다(준법문서 임의주입 금지 — 확정값만).

```bash
# confirmed.json: {"business_registration": "000-00-00000"}
python "<SKILL_DIR>/generate_checklists.py" \
  --contract "투자계약서.docx" --report "투심보고서.docx" \
  --company-data confirmed.json --enrich --output-dir ./output
```

`--company-data` JSON 에 넣을 수 있는 키: `company_name`, `representative`, `address`,
`establishment_date`, `business_registration`, `corp_reg_number`, `industry_code`,
`business_description`, `contract_date`. **미상 필드는 빈칸으로 남아** 준법감시인이 직접 채운다.

### 4단계 — 결과 보고

생성 경로를 안내하고, 2단계에서 출력된 **데이터 불일치·미상 항목**을 사용자에게 요약 보고한다.

## 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--contract` | (필수) 투자계약서 경로 |
| `--report` | (필수) 투자심사보고서 경로 |
| `--output-dir` | 출력 폴더 (기본 `./output`) |
| `--company-name` | 회사명 직접 지정 (추출 실패 시) |
| `--company-data` | 확정 회사정보 JSON 주입 |
| `--enrich` | 확정 사업자번호로 bizno.net 보완 |

## 생성 문서 구성 (준법사항체크리스트)

표지(펀드/GP) · 1.투자기업 · 2.투자내용(투자유형/금액/단가/조건/위약벌/동반투자) ·
3.투자담당자 · 4.벤처기업 등 해당여부 · 5.준법사항 확인(법령상·규약상 투자제한) ·
6.기타사항 + 서명란 · [별첨1] ESG 자가점검 · [별첨2] 중소기업은행 인정 확인서

**표5 규약상 투자제한 비고 자동화** (투심보고서 별첨 참조):
- 제35조1항1·2·3호(국토교통/모빌리티/남부권)·제61조1항2호(TCB): 투심보고서 **별첨2(투자재원검토보고서)** 의 해당여부가 "해당"이면, 해당 조항 비고 셀 맨 밑줄에 별첨2 근거를 `▪ …`(TCB는 `▪ 본건 TCB 등급: …`)로 자동 기재. "미해당"이면 미기재.
- 제61조1항1호(중소기업은행): 투심보고서 **별첨5(IBK 신규/기존거래 인정 사유)** 가 "해당(O)"이면 비고 `투자대상 : 중소기업은행 신규 및 기존거래 기업` 끝에 `(O)` 표시.

## 주의사항

- **실제 투자정보·개인정보는 외부로 전송되지 않는다.** bizno.net 조회는 *확정 사업자등록번호* 기준
  공개 기업정보 조회에 한한다. 전 과정이 본인 PC 에서만 동작한다.
- 일치여부·적부를 임의로 단정하지 말 것. 계약서·투심보고서를 대조한 결과를 반영한다.
- 생성된 문서는 **초안**이며, 준법감시인이 최종 확인·서명해야 효력이 있다.
- `output/`, 원본 계약서·투심보고서, 확정 JSON 등 실데이터 파일은 **공개 저장소에 올리지 않는다.**

## 의존성

```bash
pip install python-docx lxml olefile requests
# PDF/스캔본 입력 시: pip install pymupdf pytesseract Pillow
```
