@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  JumpTunnel - 启动
echo ========================================
echo.

REM 检查 python 是否可用
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3 并加入 PATH。
    pause
    exit /b 1
)

REM 以可编辑模式安装本项目（含入口命令 jumptunnel）
echo [1/2] 安装依赖并注册本工具...
python -m pip install -e .
if errorlevel 1 (
    echo [错误] 安装失败，请检查网络或手动执行：pip install -e .
    pause
    exit /b 1
)

echo.
echo [2/2] 启动程序...
python -m jumptunnel

if errorlevel 1 (
    echo.
    echo [程序已退出，如有错误请查看上方输出]
    pause
)
