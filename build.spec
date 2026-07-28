# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

CustomTkinter 运行时需要从安装目录读取主题 JSON，单文件模式下必须显式打包进来。
此 spec 通过动态定位 customtkinter 安装路径来收集其资源。

构建：uv run pyinstaller build.spec
输出：dist/JumpTunnel.exe
"""

from PyInstaller.utils.hooks import collect_data_files

# 收集 customtkinter 的全部数据文件（主题 json 等）
datas = collect_data_files("customtkinter")

a = Analysis(
    ["src/run.py"],                      # 顶层启动器，以包方式 import jumptunnel.main
    pathex=["src"],                      # 让 src 下的包可被解析
    binaries=[],
    datas=datas,
    hiddenimports=["customtkinter", "jumptunnel", "jumptunnel.main",
                   "jumptunnel.config_store", "jumptunnel.tunnel_manager"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="JumpTunnel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # 不用 upx 压缩，避免杀软误报
    runtime_tmpdir=None,
    console=False,             # GUI 程序，不显示控制台黑窗
    disable_windowed_traceback=False,
    icon=None,                 # 无图标；如有 .ico 可改为 "app.ico"
)
