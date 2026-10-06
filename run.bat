@echo off
REM Entrypoint unificado: Telegram + Voz F9 en un solo proceso.
REM Si necesitas SOLO Telegram (sin voz), usa: python -m src.bot
REM Un pidfile en logs/jeffri.pid impide arrancar dos veces (protege contra
REM el bug historico donde 2 procesos peleaban por getUpdates de Telegram).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m src.main
pause
