# tests/conftest.py
"""
pytest設定ファイル

MetaTrader5モジュールのグローバルモックなど、
全テストで共有される設定を定義
"""

import sys
from unittest.mock import MagicMock

# MetaTrader5モジュールをモック（Windows専用モジュールのため）
sys.modules['MetaTrader5'] = MagicMock()
