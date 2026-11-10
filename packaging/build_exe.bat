@echo off
rem Builds dist\dotacheat\dotacheat.exe (one-folder app). Needs Python 3.11+ on PATH.
cd /d "%~dp0\.."
python -m venv .venv-build || goto :err
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install . pyinstaller || goto :err
pyinstaller --noconfirm --distpath dist --workpath build packaging\dotacheat.spec || goto :err
echo.
echo Gata: dist\dotacheat\dotacheat.exe
goto :eof
:err
echo Build esuat.
exit /b 1
