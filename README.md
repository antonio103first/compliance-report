# 준법감시보고서 작성 (Claude Code 스킬)

K-Run Ventures **케이런7호 펀드** 투자건의 **투자계약서·투자심사보고서**로부터
**준법사항체크리스트(준법감시보고서) 한글(.hwpx)** 을 **자동 작성**하는 Claude Code 스킬입니다.

> ⚠️ 이 저장소에는 **실제 투자정보·개인정보가 전혀 없습니다.** 양식의 예시는 모두 `㈜AAA` · `[대표이사]` 등 placeholder 입니다.
> 실제 데이터는 각자 본인 PC 에서만 처리됩니다(외부 전송 없음).

> 🔗 **관련 스킬:** 본 스킬은 **준법사항체크리스트(.hwpx)** 만 생성합니다.
> **투자계약서 체크리스트(.docx)** 가 필요하면 👉 [investment-contract-checklist](https://github.com/antonio103first/investment-contract-checklist) 를 사용하세요.

---

# ✅ 가장 쉬운 설치 (자동 설치 스크립트)

> **Windows 기준 3단계, 약 3분.** 명령어를 몰라도 됩니다.

## 1단계 · GitHub에서 다운로드

1. 브라우저에서 접속 👉 **https://github.com/antonio103first/compliance-report**
2. 초록색 **`< > Code`** 버튼 클릭 → **`Download ZIP`** 클릭
3. 받은 ZIP 파일을 **오른쪽 클릭 → "압축 풀기"**
   → `compliance-report-main` 폴더가 생깁니다.

## 2단계 · 설치 파일 더블클릭

압축을 푼 폴더 안에 있는 설치 파일을 더블클릭합니다.

| 운영체제 | 더블클릭할 파일 |
|----------|-----------------|
| **Windows** | `install_windows.bat` |
| **macOS / Linux** | 터미널에서 `bash install_mac_linux.sh` |

> 검은 창이 뜨면서 자동으로 스킬을 복사하고 필요한 패키지를 설치합니다.
> "설치 완료!" 메시지가 보이면 됩니다. (Windows에서 "Windows의 PC 보호" 경고가 뜨면
> **추가 정보 → 실행**을 누르세요.)

## 3단계 · Claude Code 재시작

Claude Code를 **완전히 종료했다가 다시 실행**합니다.
대화창에 **`/`** 를 입력했을 때 목록에 **compliance-report** 가 보이면 **설치 완료**입니다. 🎉

---

# 🚀 사용 방법

투자계약서와 투자심사보고서 파일(`.docx`)을 한 폴더에 두고, Claude Code에 **자연어로** 요청하세요.

```
투자계약서_OOO.docx 와 투심보고서_OOO.docx 로
준법감시보고서(준법사항체크리스트) 작성해줘. ./output 에 저장해줘.
```

Claude가 자동으로:
1. 두 문서에서 핵심 항목(회사명·투자금액·단가·주식수·위약벌·담당자 등)을 추출
2. **일치 여부를 교차검증**(불일치 발견 시 콘솔에 경고)
3. `output/준법사항체크리스트_{펀드}_{회사}.hwpx` (**준법감시보고서 정본**)를 생성합니다.
4. 미상 항목·발견사항을 요약 보고합니다.

> 📄 원본이 `.hwp/.hwpx` 라면, 한글에서 **다른 이름으로 저장 → `.docx`** 로 변환 후 사용하면 가장 정확합니다.

### 🔎 자동조회·검증 기능 (공공데이터 연동)

회사개요에 **사업자등록번호**만 적어두면 외부 공적 출처에서 자동 보완·판정합니다(준법문서
원칙: **확인된 값만**, 모호/만료/미발견은 공란 + 담당자 확인 안내).

- **`--corp-enrich`** — 금융위 기업기본정보 API로 **설립일·법인등록번호·대표·주소·업종**
  보완 → 표1·표6 + **창업기업 7년 자동판정**. (환경변수 `DATA_GO_KR_CORP_KEY`)
- **`--cert-enrich`** — **벤처기업/이노비즈/메인비즈** 해당여부 자동판정(표4). 벤처기업명단·
  혁신형중소기업 명단(회사명+주소 매칭) + **이노비즈넷 실시간 조회**로 보완. 명단은 월 1회
  자동 갱신(Task Scheduler) 가능.
- **`--special-terms "요약"`** — 계약서 본문의 **특약사항을 한 줄 요약**해 표2 '기타'에 기재
  (뒤쪽 별지/별첨 약정은 제외).
- **`--enrich`** — 확정 사업자번호 기준 bizno.net 보완(설립일·주소·법인번호).

매 실행 시 **인증 자료 기준일**을 표시하고, 애매한 매칭은 **공개조회 딥링크**(벤처공시·
이노비즈넷)를 경고에 포함합니다. 자세한 사용법은 스킬의 `SKILL.md` 참조.

### 생성되는 준법사항체크리스트 구성

1.투자기업 / 2.투자내용 / 3.투자담당자 / 4.벤처기업 등 해당여부 /
5.준법사항 확인(법령상·규약상 투자제한) / 6.기타사항 + 서명란 /
[별첨1] ESG 자가점검 / [별첨2] 중소기업은행 신규·기존거래 기업 인정 확인서

> 생성된 `.hwpx` 는 한컴오피스에서 **복구 모드 없이 바로 열립니다.**

---

# ⌨️ (대안) 명령어로 설치 — Claude Code 플러그인

자동 설치 스크립트 대신 명령어로 설치할 수도 있습니다. **최신 버전 Claude Code에서만 지원됩니다.**
(아래가 `unknown command` 등으로 안 되면 위의 "자동 설치 스크립트"를 사용하세요.)

```
/plugin marketplace add antonio103first/compliance-report
/plugin install compliance-report@krun-compliance
```

설치 후 `/plugin` 을 입력하면 설치 화면에서 관리(활성화/삭제/업데이트)할 수 있습니다.

---

# 🔧 수동 설치 (스크립트가 막힐 때)

회사 보안정책 등으로 `.bat` 실행이 막히면 폴더만 직접 복사하면 됩니다.

1. 위 1단계처럼 ZIP을 받아 압축을 풉니다.
2. 압축 푼 폴더 안에서 아래 **스킬 폴더**를 찾습니다.
   ```
   plugins\compliance-report\skills\compliance-report
   ```
3. 파일 탐색기 주소창에 `%USERPROFILE%\.claude\skills` 를 입력해 이동합니다.
   (`skills` 폴더가 없으면 새로 만듭니다.)
4. 2번의 **스킬 폴더(`compliance-report`)를 통째로** 3번 위치에 복사합니다.
   → 최종 경로가 `%USERPROFILE%\.claude\skills\compliance-report\SKILL.md` 가 되면 됩니다.
5. 명령 프롬프트에서 `pip install python-docx lxml olefile requests` 실행 후 Claude Code 재시작.

---

# 🔒 보안 주의사항 (필독)

- 실제 투자정보·개인정보(사업자번호·주소 등)는 **외부로 전송되지 않습니다.** 전 과정이 **본인 PC에서만** 동작합니다.
  (bizno.net 조회는 *확정 사업자등록번호* 기준 공개 기업정보 조회에 한합니다.)
- 실제 데이터가 담긴 파일(원본 계약서·투심보고서, `output/`, 확정 JSON)은 **공개 저장소에 올리지 마세요.**
- 생성된 문서는 **초안**입니다. 준법감시인이 최종 확인·서명해야 효력이 있습니다.

---

# ❓ 문제 해결

| 증상 | 해결 |
|------|------|
| 스킬이 `/` 목록에 안 보임 | Claude Code를 **완전히 종료 후 재시작**. 그래도 안 보이면 "수동 설치"의 최종 경로 확인 |
| `install_windows.bat` 실행 시 보안 경고 | "추가 정보 → 실행" 클릭 (회사 PC는 IT 정책상 차단될 수 있음 → "수동 설치" 사용) |
| `/plugin` 명령이 안 먹힘 | Claude Code 버전이 낮은 경우. "자동 설치 스크립트" 또는 "수동 설치" 사용 |
| `python-docx 가 필요합니다` 오류 | `pip install python-docx lxml olefile requests` 실행 (Python 미설치 시 python.org에서 먼저 설치) |
| 생성된 hwpx가 한글에서 "복구" 창이 뜸 | 최신 버전으로 다시 받으세요(레이아웃 캐시 정리 적용). 그래도 뜨면 [한 번 복구하여 열고 → 다른 이름으로 저장] |
| 한글이 화면에 `???` 로 깨져 보임 | 콘솔 출력만의 문제이며 **생성된 문서는 정상**입니다 |

---

# 📂 저장소 구조

```
compliance-report/
├── install_windows.bat                       # ★ Windows 자동 설치
├── install_mac_linux.sh                       # ★ macOS/Linux 자동 설치
├── README.md                                  # 본 매뉴얼
├── requirements.txt · LICENSE · .gitignore
├── .claude-plugin/
│   └── marketplace.json                       # 플러그인 마켓플레이스 매니페스트
└── plugins/compliance-report/
    ├── .claude-plugin/plugin.json             # 플러그인 매니페스트
    └── skills/compliance-report/              # ← 스킬 본체 (수동 설치 시 이 폴더 복사)
        ├── SKILL.md
        ├── generate_checklists.py             # 메인 CLI
        ├── extractors/                        # 계약서·투심보고서·PDF·bizno 파서
        ├── generators/                        # hwpx 생성기
        └── (양식) 준법사항체크리스트.hwpx          # 익명화 양식 (placeholder)
```

---

## 라이선스

[MIT License](./LICENSE) · © K-Run Ventures
