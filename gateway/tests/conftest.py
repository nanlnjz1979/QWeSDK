"""让 Gateway 测试从仓库根目录导入已打包的 QWeSDK 模块。"""

from __future__ import annotations

import sys
from pathlib import Path


GATEWAY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = GATEWAY_ROOT.parent

for path in (PROJECT_ROOT, GATEWAY_ROOT):
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)
