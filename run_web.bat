@echo off
REM ProTrader web/mobile server (no Qt needed). Open http://<this-pc-ip>:8765 on your phone (same Wi-Fi).
cd /d %~dp0
python -m pip install -q -r requirements-web.txt
python main.py --web --port 8765
pause
