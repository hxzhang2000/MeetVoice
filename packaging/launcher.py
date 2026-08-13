"""MeetVoice 单文件 exe 启动器（供 PyInstaller 打包入口）。

仅做一件事：调用 `meetvoice.cli:main`。所有重型依赖在运行时按需懒加载，
未安装不影响此入口工作。
"""

import sys


def _main() -> int:
    from meetvoice.cli import main

    return main()


if __name__ == "__main__":
    sys.exit(_main())
