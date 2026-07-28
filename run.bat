@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  SSH 端口转发工具 - 启动
echo ========================================
echo.

REM 检查 python 是否可用
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3 并加入 PATH。
    pause
    exit /b 1
)

REM 安装依赖（已安装会快速跳过）
echo [1/2] 检查并安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或手动执行：pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [2/2] 启动程序...
python main.py

if errorlevel 1 (
    echo.
    echo [程序已退出，如有错误请查看上方输出]
    pause
)
