#!/usr/bin/env bash
# 준법감시보고서 작성 스킬 - 자동 설치 (macOS / Linux)
set -e

echo "============================================================"
echo "  준법감시보고서 작성 스킬 - 자동 설치 (macOS/Linux)"
echo "============================================================"
echo

DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$DIR/plugins/compliance-report/skills/compliance-report"
SKILL_DST="$HOME/.claude/skills/compliance-report"

if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
  echo "[오류] 스킬 원본을 찾을 수 없습니다. 압축 해제한 폴더 안에서 실행했는지 확인하세요."
  exit 1
fi

echo "[1/3] 스킬 폴더 복사 중..."
mkdir -p "$HOME/.claude/skills"
rm -rf "$SKILL_DST"
cp -R "$SKILL_SRC" "$SKILL_DST"
echo "      완료: $SKILL_DST"
echo

echo "[2/3] 필요한 Python 패키지 설치 중..."
if ! pip install python-docx lxml olefile requests; then
  echo "[경고] 패키지 설치 실패. Python/pip 설치 여부를 확인하세요: https://www.python.org/downloads/"
fi
echo

echo "[3/3] 설치 완료!"
echo
echo "  다음 단계:"
echo "  1) Claude Code를 완전히 종료했다가 다시 실행하세요."
echo "  2) 대화창에 / 를 입력해 목록에 compliance-report 가 보이면 성공입니다."
echo
echo "  * PDF/스캔본 입력이 필요하면 추가로: pip install pymupdf pytesseract Pillow"
echo "============================================================"
