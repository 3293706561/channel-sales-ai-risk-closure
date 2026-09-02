@echo off
setlocal
set "PROJECT_DIR=%~dp0app"
set "PYTHON_EXE=C:\Users\lenovopc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" set "PYTHON_EXE=py"

start "渠道销售AI经营风险闭环系统" /b "%PYTHON_EXE%" -m http.server 8765 --directory "%PROJECT_DIR%"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8765/index.html"

echo.
echo 项目已启动。浏览器关闭后，这个窗口请保持打开。
echo 如需停止服务，关闭本窗口即可。
pause
