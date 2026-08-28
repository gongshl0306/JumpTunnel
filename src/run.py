"""PyInstaller 打包入口。

PyInstaller 单文件 exe 把本文件作为顶层脚本运行，它以普通模块身份
import 包内的 jumptunnel.main，从而让包内相对导入正常工作。
开发时不要直接运行此文件，请用 `uv run jumptunnel` 或 `python -m jumptunnel`。
"""

from jumptunnel.main import main

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # GUI 程序（console=False）崩溃时无任何输出，把堆栈写到
        # exe 旁边的 crash.log 方便定位闪退原因
        import os
        import sys
        import traceback

        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        log_path = os.path.join(exe_dir, "crash.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
