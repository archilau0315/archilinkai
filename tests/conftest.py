"""pytest 全局配置：把项目根加入 sys.path，便于测试导入模块。"""

import os
import sys

# 项目根 = conftest.py 所目录的上一级
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
