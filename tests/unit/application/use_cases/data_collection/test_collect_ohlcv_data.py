# tests/unit/application/use_cases/data_collection/test_collect_ohlcv_data.py
"""CollectOhlcvDataUseCase 単体テスト"""

import pytest
import pandas as pd
from datetime import datetime
import pytz
from unittest.mock import Mock, MagicMock

from src.application.use_cases.data_collection.collect_ohlcv_data import CollectOhlcvDataUseCase


class TestCollectOhlcvDataUseCase:
    """CollectOhlcvDataUseCase のテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行"""
        # モックオブジェクト作成
        self.mt5_collector = Mock()
        self.s3_repo = Mock()
        self.ohlcv_cache = Mock()
        
        # 設定
        self.symbols = ['USDJPY', 'EURUSD']
        self.timeframes = ['H1', 'D1']
        self.fetch_counts = {'H1': 24, 'D1': 30, 'DEFAULT': 1000}
        
        # テスト用DataFrame
        self.test_df = pd.DataFrame({
            'timestamp_utc': pd.date_range('2025-10-15', periods=24, freq='H'),
            'open': [100.0] * 24,
            'high': [101.0] * 24,
            'low': [99.0] * 24,
            'close': [100.5] * 24,
            'volume': [1000] * 24
        })
        
        # ユースケース作成
        self.use_case = CollectOhlcvDataUseCase(
            mt5_data_collector=self.mt5_collector,
            s3_repository=self.s3_repo,
            ohlcv_cache=self.ohlcv_cache,
            symbols=self.symbols,
            timeframes=self.timeframes,
            fetch_counts=self.fetch_counts
        )
    
    def test_execute_success_all(self):
        """全データ収集成功"""
        # MT5からのデータ取得をモック
        self.mt5_collector.fetch_ohlcv_data.return_value = self.test_df
        
        # S3保存成功をモック
        self.s3_repo.save_ohlcv_data.return_value = True
        
        # Redis保存成功をモック
        self.ohlcv_cache.save_ohlcv.return_value = True
        self.ohlcv_cache.get_cache_stats.return_value = {
            'total_keys': 4,
            'memory_used_mb': 5.0,
            'memory_status': 'OK'
        }
        
        # 実行
        result = self.use_case.execute()
        
        # 検証
        assert result is True
        
        # MT5が正しく呼ばれたか
        assert self.mt5_collector.fetch_ohlcv_data.call_count == 4  # 2 symbols × 2 timeframes
        
        # S3が正しく呼ばれたか
        assert self.s3_repo.save_ohlcv_data.call_count == 4
        
        # Redisが正しく呼ばれたか
        assert self.ohlcv_cache.save_ohlcv.call_count == 4
    
    def test_execute_mt5_failure(self):
        """MT5からのデータ取得失敗"""
        # MT5からのデータ取得失敗をモック
        self.mt5_collector.fetch_ohlcv_data.return_value = None
        
        # 実行
        result = self.use_case.execute()
        
        # 検証: 全て失敗したのでFalse
        assert result is False
        
        # S3とRedisは呼ばれない
        assert self.s3_repo.save_ohlcv_data.call_count == 0
        assert self.ohlcv_cache.save_ohlcv.call_count == 0
    
    def test_execute_s3_failure(self):
        """S3保存失敗"""
        # MT5からのデータ取得成功
        self.mt5_collector.fetch_ohlcv_data.return_value = self.test_df
        
        # S3保存失敗をモック
        self.s3_repo.save_ohlcv_data.return_value = False
        
        # 実行
        result = self.use_case.execute()
        
        # 検証: 全て失敗したのでFalse
        assert result is False
        
        # Redisは呼ばれない（S3失敗時はスキップ）
        assert self.ohlcv_cache.save_ohlcv.call_count == 0
    
    def test_execute_redis_failure(self):
        """Redis保存失敗（S3は成功）"""
        # MT5からのデータ取得成功
        self.mt5_collector.fetch_ohlcv_data.return_value = self.test_df
        
        # S3保存成功
        self.s3_repo.save_ohlcv_data.return_value = True
        
        # Redis保存失敗
        self.ohlcv_cache.save_ohlcv.return_value = False
        self.ohlcv_cache.get_cache_stats.return_value = {}
        
        # 実行
        result = self.use_case.execute()
        
        # 検証: Redis失敗でも成功扱い（警告ログのみ）
        assert result is True
        
        # S3は全て成功
        assert self.s3_repo.save_ohlcv_data.call_count == 4
        
        # Redisは呼ばれたが失敗
        assert self.ohlcv_cache.save_ohlcv.call_count == 4
    
    def test_execute_partial_success(self):
        """一部成功・一部失敗"""
        # MT5: 最初の2回は成功、後の2回は失敗
        self.mt5_collector.fetch_ohlcv_data.side_effect = [
            self.test_df,  # USDJPY H1 成功
            self.test_df,  # USDJPY D1 成功
            None,          # EURUSD H1 失敗
            None           # EURUSD D1 失敗
        ]
        
        # S3保存成功
        self.s3_repo.save_ohlcv_data.return_value = True
        
        # Redis保存成功
        self.ohlcv_cache.save_ohlcv.return_value = True
        self.ohlcv_cache.get_cache_stats.return_value = {}
        
        # 実行
        result = self.use_case.execute()
        
        # 検証: 一部成功したのでTrue
        assert result is True
        
        # S3は2回だけ呼ばれる（MT5成功分のみ）
        assert self.s3_repo.save_ohlcv_data.call_count == 2
        
        # Redisも2回だけ呼ばれる
        assert self.ohlcv_cache.save_ohlcv.call_count == 2
    
    def test_execute_exception_handling(self):
        """例外発生時の処理継続"""
        # MT5: 最初は例外、2回目以降は成功
        self.mt5_collector.fetch_ohlcv_data.side_effect = [
            Exception("Test error"),  # USDJPY H1 例外
            self.test_df,             # USDJPY D1 成功
            self.test_df,             # EURUSD H1 成功
            self.test_df              # EURUSD D1 成功
        ]
        
        # S3保存成功
        self.s3_repo.save_ohlcv_data.return_value = True
        
        # Redis保存成功
        self.ohlcv_cache.save_ohlcv.return_value = True
        self.ohlcv_cache.get_cache_stats.return_value = {}
        
        # 実行
        result = self.use_case.execute()
        
        # 検証: 例外があっても他の処理は継続
        assert result is True
        
        # 3つは成功
        assert self.s3_repo.save_ohlcv_data.call_count == 3
        assert self.ohlcv_cache.save_ohlcv.call_count == 3
    
    def test_fetch_counts_default(self):
        """fetch_countsでDEFAULTが使用される"""
        # タイムフレームにM15を追加（fetch_countsには定義なし）
        use_case = CollectOhlcvDataUseCase(
            mt5_data_collector=self.mt5_collector,
            s3_repository=self.s3_repo,
            ohlcv_cache=self.ohlcv_cache,
            symbols=['USDJPY'],
            timeframes=['M15'],  # 定義なし
            fetch_counts={'H1': 24, 'DEFAULT': 500}
        )
        
        # MT5からのデータ取得成功
        self.mt5_collector.fetch_ohlcv_data.return_value = self.test_df
        self.s3_repo.save_ohlcv_data.return_value = True
        self.ohlcv_cache.save_ohlcv.return_value = True
        self.ohlcv_cache.get_cache_stats.return_value = {}
        
        # 実行
        use_case.execute()
        
        # 検証: DEFAULTの500が使われる
        self.mt5_collector.fetch_ohlcv_data.assert_called_once_with(
            symbol='USDJPY',
            timeframe='M15',
            count=500
        )


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])