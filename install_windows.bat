@echo off
chcp 65001 >nul
setlocal
title 준법감시보고서 작성 스킬 설치

echo ============================================================
echo   준법감시보고서 작성 스킬 - 자동 설치 (Windows)
echo ============================================================
echo.

set "SKILL_SRC=%~dp0plugins\compliance-report\skills\compliance-report"
set "SKILL_DST=%USERPROFILE%\.claude\skills\compliance-report"

if not exist "%SKILL_SRC%\SKILL.md" (
  echo [오류] 스킬 원본을 찾을 수 없습니다.
  echo        이 파일을 압축 해제한 폴더 안에서 실행했는지 확인하세요.
  echo.
  pause
  exit /b 1
)

echo [1/3] 스킬 폴더 복사 중...
if not exist "%USERPROFILE%\.claude\skills" mkdir "%USERPROFILE%\.claude\skills"
if exist "%SKILL_DST%" rmdir /s /q "%SKILL_DST%"
xcopy /e /i /y "%SKILL_SRC%" "%SKILL_DST%" >nul
echo       완료: %SKILL_DST%
echo.

echo [2/3] 필요한 Python 패키지 설치 중...
pip install python-docx lxml olefile requests
if errorlevel 1 (
  echo.
  echo [경고] 패키지 설치에 실패했습니다.
  echo        Python이 설치되어 있는지 확인하세요: https://www.python.org/downloads/
  echo        (설치 시 "Add Python to PATH" 체크 필수)
)
echo.

echo [3/3] 설치 완료!
echo.
echo   다음 단계:
echo   1) Claude Code를 완전히 종료했다가 다시 실행하세요.
echo   2) 대화창에 / 를 입력해 목록에
echo      compliance-report 가 보이면 성공입니다.
echo.
echo   * PDF/스캔본 입력이 필요하면 추가로:
echo     pip install pymupdf pytesseract Pillow
echo ============================================================
pause
