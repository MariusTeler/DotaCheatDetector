@echo off
rem Ruleaza DotaCheatDetector din sursa (fara exe). Prima rulare instaleaza dependintele.
rem   run.bat                      -> interfata web locala
rem   run.bat analyze --match ID   -> linie de comanda
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Prima rulare: creez mediul Python si instalez dependintele...
  python -m venv .venv || (echo Instaleaza Python 3.11+ de pe python.org si bifeaza "Add to PATH". & pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -e . || (pause & exit /b 1)
)
.venv\Scripts\python -m dotacheat %*
