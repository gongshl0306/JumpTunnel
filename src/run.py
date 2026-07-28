"""PyInstaller 打包入口。

PyInstaller 单文件 exe 把本文件作为顶层脚本运行，它以普通模块身份
import 包内的 jumptunnel.main，从而让包内相对导入正常工作。
开发时不要直接运行此文件，请用 `uv run jumptunnel` 或 `python -m jumptunnel`。
"""

from jumptunnel.main import main

if __name__ == "__main__":
    main()
