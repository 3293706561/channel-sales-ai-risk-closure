@echo off
setlocal
set "ROOT=%~dp0"
echo 正在启动本地演示服务：http://127.0.0.1:8000
echo 按 Ctrl+C 可以停止服务。
"%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%ROOT%backend" --host 127.0.0.1 --port 8000
