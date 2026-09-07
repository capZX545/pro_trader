@echo off
REM Local one-shot build (Windows):  packaging\build.bat  → dist\ProTrader\ and release\ProTrader-Setup-*.exe (needs Inno Setup 6 in PATH for the installer)
cd /d "%~dp0\.."
python -m pip install -q -r requirements.txt pyinstaller pillow
python packaging\make_icons.py
pyinstaller --noconfirm protrader.spec
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\installer.iss) else (echo Inno Setup not found - portable build in dist\ProTrader)
echo done
