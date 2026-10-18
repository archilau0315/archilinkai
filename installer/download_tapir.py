"""薄壳：转发到包内 archilinkai.download_tapir（向后兼容旧构建脚本）。

新用法推荐：archilinkai download-tapir 28 [--platform win|mac|all] [--out DIR]
"""

from __future__ import annotations

import sys

from archilinkai.download_tapir import main

if __name__ == "__main__":
    sys.exit(main())
