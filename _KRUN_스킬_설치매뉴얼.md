# K-Run Ventures · Claude Code 스킬 설치 매뉴얼

준법감시·투자계약 검토 업무를 자동화하는 **Claude Code 스킬 2종**의 설치 안내입니다.
명령어를 몰라도 **ZIP 다운로드 → 설치 파일 더블클릭 → Claude Code 재시작** 3단계면 끝납니다.

| 스킬 | 하는 일 | 만드는 문서 | GitHub |
|------|---------|-------------|--------|
| **compliance-report** (준법감시보고서) | 투자계약서·투심보고서 대조 → 준법사항 검토 | 준법사항체크리스트 **`.hwpx`** | https://github.com/antonio103first/compliance-report |
| **investment-contract-checklist** (투자계약서 체크리스트) | 투심보고서 ↔ 투자계약서 일치성·의무기재사항 검토 | 투자계약서 체크리스트 **`.docx`** | https://github.com/antonio103first/investment-contract-checklist |

> 두 스킬은 역할이 다릅니다. **둘 다 설치**하면 hwpx·docx 산출물을 모두 만들 수 있습니다.

> ⚠️ **주소 정확히 확인:** 저장소명은 `compliance-report` 입니다. 끝에 **`-skill` 을 붙이면 안 됩니다**
> (`compliance-report-skill` 은 존재하지 않아 404·"private처럼 막힘"으로 보입니다). 위 표의 링크를 그대로 사용하세요.

> 🔒 **보안:** 두 스킬 모두 **본인 PC에서만** 동작하며, 실제 투자정보·개인정보를 **외부로 전송하지 않습니다.**
> 저장소에는 실데이터가 없고 양식은 모두 `㈜AAA` 등 placeholder 입니다.

---

## ✅ 사전 준비 (최초 1회)

1. **Claude Code (PC용 앱)** 설치 — 이미 쓰고 계시면 건너뜁니다.
2. **Python** 설치 — https://www.python.org/downloads/
   - 설치 화면에서 **`Add Python to PATH` 반드시 체크**

---

## 🚀 설치 (스킬마다 동일, 각각 1번씩)

> 아래 절차를 **두 스킬 각각** 반복하면 됩니다. (예시는 compliance-report 기준)

### 1단계 · GitHub에서 다운로드
1. 위 표의 GitHub 주소 접속
2. 초록색 **`< > Code`** 버튼 → **`Download ZIP`**
3. 받은 ZIP **오른쪽 클릭 → "압축 풀기"**

### 2단계 · 설치 파일 더블클릭
압축 푼 폴더 안의 설치 파일을 더블클릭합니다.

| 운영체제 | 더블클릭 / 실행 |
|----------|-----------------|
| **Windows** | `install_windows.bat` |
| **macOS / Linux** | 터미널에서 `bash install_mac_linux.sh` |

> 검은 창이 뜨며 스킬을 복사하고 필요한 패키지를 설치합니다. "설치 완료!"가 보이면 성공.
> Windows에서 "Windows의 PC 보호" 경고가 뜨면 **추가 정보 → 실행**.

### 3단계 · Claude Code 재시작
Claude Code를 **완전히 종료 후 다시 실행** → 대화창에 **`/`** 입력 시 목록에
**compliance-report** / **investment-contract-checklist** 가 보이면 설치 완료 🎉

---

## ⌨️ (대안) 명령어로 설치 — 최신 Claude Code

```
/plugin marketplace add antonio103first/compliance-report
/plugin install compliance-report@krun-compliance
```
```
/plugin marketplace add antonio103first/investment-contract-checklist
/plugin install investment-contract-checklist@krun-skills
```
> `unknown command` 가 뜨면 위 "설치 파일 더블클릭" 방식을 쓰세요.

---

## 🔧 수동 설치 (회사 보안정책으로 .bat 차단 시)

1. ZIP을 받아 압축을 풉니다.
2. 폴더 안의 **스킬 본체 폴더**를 찾습니다:
   `plugins\<스킬이름>\skills\<스킬이름>`
3. 파일 탐색기 주소창에 `%USERPROFILE%\.claude\skills` 입력해 이동 (`skills` 폴더 없으면 새로 만들기).
4. 2번 폴더를 **통째로** 3번 위치에 복사 →
   최종 경로가 `…\.claude\skills\<스킬이름>\SKILL.md` 가 되면 됩니다.
5. 패키지 설치 후 Claude Code 재시작:
   - compliance-report: `pip install python-docx lxml olefile requests`
   - investment-contract-checklist: `pip install python-docx`

---

## 💬 사용 방법

원본 문서(`.docx`)를 한 폴더에 두고 Claude Code에 **자연어로** 요청합니다.

**준법감시보고서 (hwpx):**
```
투자계약서_OOO.docx 와 투심보고서_OOO.docx 로
준법감시보고서(준법사항체크리스트) 작성해줘. ./output 에 저장해줘.
```

**투자계약서 체크리스트 (docx):**
```
투심보고서_OOO.docx 와 투자계약서_OOO.docx 를 바탕으로
투자계약서 체크리스트 작성해줘. ./output 에 저장해줘.
```

> 📄 원본이 `.hwp/.hwpx` 면 한글에서 **다른 이름으로 저장 → `.docx`** 변환 후 쓰면 가장 정확합니다.
> 생성 문서는 **초안**이며, 준법감시인의 최종 확인·서명이 있어야 효력이 있습니다.

---

## ❓ 문제 해결

| 증상 | 해결 |
|------|------|
| GitHub가 **404 / private(접근 권한 없음)** 처럼 막힘 | ① 주소 끝에 `-skill` 등 오타 없는지 확인 (정확히 `compliance-report`) ② 브라우저 새로고침(캐시) ③ 사내망에서 `github.com`·`codeload.github.com` 이 차단된 경우 → 담당자(antonio103@gmail.com)에게 ZIP 직접 요청 |
| 스킬이 `/` 목록에 안 보임 | Claude Code **완전 종료 후 재시작**. 그래도 안 보이면 "수동 설치" 최종 경로 확인 |
| `.bat` 실행 시 보안 경고 | "추가 정보 → 실행" (회사 PC 차단 시 "수동 설치" 사용) |
| `/plugin` 명령 안 먹힘 | Claude Code 버전이 낮음 → "설치 파일 더블클릭" 또는 "수동 설치" |
| `python-docx 가 필요합니다` 오류 | 위 pip 명령 실행 (Python 미설치면 python.org에서 먼저 설치) |
| 한글이 화면에 `???` 로 깨짐 | 화면 출력만의 문제, **생성된 문서는 정상** |

---

© K-Run Ventures · 문의: antonio103@gmail.com
