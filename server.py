"""兼容壳：等价于 python -m archilinkai（保留旧版 MCP 配置 `python server.py` 可用）。"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from archilinkai.server import main

if __name__ == "__main__":
    main()
