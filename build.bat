@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  SSH 端口转发工具 - 打包 exe
echo ========================================
echo.

REM 检查 uv 是否可用，没有则提示安装
where uv >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 uv，请先安装：https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo [1/2] 同步环境（含 PyInstaller）...
uv sync
if errorlevel 1 (
    echo [错误] 环境同步失败
    pause
    exit /b 1
)

echo.
echo [2/2] 打包...
uv run pyinstaller build.spec --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo  打包完成！exe 位于：dist\JumpTunnel.exe
echo ========================================
pause
