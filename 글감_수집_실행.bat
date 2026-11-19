@echo off
chcp 65001 > nul
title innislives 블로그 글감 수집 에이전트
cd /d "%~dp0"

echo ========================================================
echo   innislives-scout-agent (블로그 글감 자동 수집기)
echo ========================================================
echo.

python -X utf8 scout_agent.py

echo.
echo 완료! ideas 폴더에서 오늘 날짜의 리포트(.md)를 확인하세요.
pause
