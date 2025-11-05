# tests/unit/infrastructure/gateways/market_data/test_yfinance_gateway.py
"""
YFinance Gateway 単体テスト

対象: src/infrastructure/gateways/market_data/yfinance_gateway.py
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import time

from src.infrastructure.gateways.market_data.yfinance_gateway import YFinanceGateway


class TestYFinanceGateway:
    """YFinanceGateway のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.gateway = YFinanceGateway(cache_duration=60)

        # テスト用DataFrameデータ
        self.test_ohlcv_df = pd.DataFrame({
            'Open': [150.0, 150.5, 151.0],
            'High': [150.5, 151.0, 151.5],
            'Low': [149.5, 150.0, 150.5],
            'Close': [150.3, 150.8, 151.2],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2025-11-01', periods=3, freq='h', tz='UTC'))

    # ========================================
    # 【初期化・シンボル変換】3テスト
    # ========================================

    def test_init_default_cache_duration(self):
        """
        初期化 - デフォルトキャッシュ期間

        条件: cache_duration指定なし
        期待: 60秒がデフォルト設定
        """
        # Act
        gateway = YFinanceGateway()

        # Assert
        assert gateway.cache_duration == 60
        assert gateway._cache == {}
        assert gateway._cache_timestamps == {}

    def test_get_yf_symbol_known_pair(self):
        """
        シンボル変換 - 既知の通貨ペア

        条件: FOREX_SYMBOLSに存在するシンボル
        期待: Yahoo Finance形式に変換
        """
        # Act
        yf_symbol = self.gateway._get_yf_symbol('USDJPY')

        # Assert
        assert yf_symbol == 'USDJPY=X'

    def test_get_yf_symbol_unknown_pair(self):
        """
        シンボル変換 - 未知のシンボル

        条件: FOREX_SYMBOLSに存在しないシンボル
        期待: そのまま返却
        """
        # Act
        yf_symbol = self.gateway._get_yf_symbol('UNKNOWN')

        # Assert
        assert yf_symbol == 'UNKNOWN'

    # ========================================
    # 【データフォーマット変換】4テスト
    # ========================================

    def test_to_standard_ohlcv_format_success(self):
        """
        OHLCV形式変換 - 成功

        条件: 有効なyfinance DataFrame
        期待: 標準OHLCV形式に変換、小文字カラム名、属性追加
        """
        # Act
        result = self.gateway._to_standard_ohlcv_format(self.test_ohlcv_df.copy(), 'USDJPY')

        # Assert
        assert 'open' in result.columns
        assert 'high' in result.columns
        assert 'low' in result.columns
        assert 'close' in result.columns
        assert 'volume' in result.columns
        assert result.attrs['symbol'] == 'USDJPY'
        assert result.attrs['source'] == 'yfinance'
        assert len(result) == 3

    def test_to_standard_ohlcv_format_no_volume(self):
        """
        OHLCV形式変換 - Volume欠落

        条件: volumeカラムがないDataFrame
        期待: volumeカラムが0で追加される
        """
        # Arrange
        df_no_volume = pd.DataFrame({
            'Open': [150.0, 150.5],
            'High': [150.5, 151.0],
            'Low': [149.5, 150.0],
            'Close': [150.3, 150.8]
        })

        # Act
        result = self.gateway._to_standard_ohlcv_format(df_no_volume, 'USDJPY')

        # Assert
        assert 'volume' in result.columns
        assert result['volume'].sum() == 0

    def test_to_standard_ohlcv_format_empty_dataframe(self):
        """
        OHLCV形式変換 - 空DataFrame

        条件: 空のDataFrame
        期待: そのまま空DataFrame返却
        """
        # Arrange
        empty_df = pd.DataFrame()

        # Act
        result = self.gateway._to_standard_ohlcv_format(empty_df, 'USDJPY')

        # Assert
        assert result.empty

    def test_to_standard_ohlcv_format_data_types(self):
        """
        OHLCV形式変換 - データ型変換

        条件: 正常なDataFrame
        期待: float64（OHLC）、int64（volume）に変換
        """
        # Act
        result = self.gateway._to_standard_ohlcv_format(self.test_ohlcv_df.copy(), 'USDJPY')

        # Assert
        assert result['open'].dtype == np.float64
        assert result['high'].dtype == np.float64
        assert result['low'].dtype == np.float64
        assert result['close'].dtype == np.float64
        assert result['volume'].dtype == np.int64

    # ========================================
    # 【OHLCV取得】5テスト
    # ========================================

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_ohlcv_success(self, mock_yf):
        """
        OHLCV取得 - 成功

        条件: yfinance正常応答
        期待: 標準OHLCV形式DataFrame返却、キャッシュ保存
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.history.return_value = self.test_ohlcv_df.copy()
        mock_yf.Ticker.return_value = mock_ticker

        # Act
        result = self.gateway.fetch_ohlcv('USDJPY', 'H1', period='1mo')

        # Assert
        assert not result.empty
        assert len(result) == 3
        assert 'open' in result.columns
        mock_yf.Ticker.assert_called_once_with('USDJPY=X')

        # キャッシュ確認
        cache_key = 'USDJPY_H1_1mo_None_None'
        assert cache_key in self.gateway._cache

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_ohlcv_with_date_range(self, mock_yf):
        """
        OHLCV取得 - 日時範囲指定

        条件: start/end指定
        期待: start/endでhistory()呼び出し
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.history.return_value = self.test_ohlcv_df.copy()
        mock_yf.Ticker.return_value = mock_ticker

        start = datetime(2025, 11, 1)
        end = datetime(2025, 11, 3)

        # Act
        result = self.gateway.fetch_ohlcv('USDJPY', 'H1', start=start, end=end)

        # Assert
        assert not result.empty
        mock_ticker.history.assert_called_once()
        call_kwargs = mock_ticker.history.call_args[1]
        assert call_kwargs['start'] == start
        assert call_kwargs['end'] == end

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_ohlcv_cache_hit(self, mock_yf):
        """
        OHLCV取得 - キャッシュヒット

        条件: 同一パラメータで2回呼び出し
        期待: 2回目はキャッシュ返却、yfinance呼び出しなし
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.history.return_value = self.test_ohlcv_df.copy()
        mock_yf.Ticker.return_value = mock_ticker

        # Act - 1回目
        result1 = self.gateway.fetch_ohlcv('USDJPY', 'H1', period='1mo')

        # Act - 2回目（キャッシュヒット）
        result2 = self.gateway.fetch_ohlcv('USDJPY', 'H1', period='1mo')

        # Assert
        assert not result1.empty
        assert not result2.empty
        # yfinance.Tickerは1回だけ呼ばれる
        assert mock_yf.Ticker.call_count == 1

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_ohlcv_error_handling(self, mock_yf):
        """
        OHLCV取得 - エラーハンドリング

        条件: yfinanceで例外発生
        期待: 空DataFrame返却、エラーログ
        """
        # Arrange
        mock_yf.Ticker.side_effect = Exception("API error")

        # Act
        result = self.gateway.fetch_ohlcv('USDJPY', 'H1', period='1mo')

        # Assert
        assert result.empty

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_ohlcv_default_period(self, mock_yf):
        """
        OHLCV取得 - デフォルトperiod使用

        条件: period未指定
        期待: PERIOD_MAPのデフォルト値使用
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.history.return_value = self.test_ohlcv_df.copy()
        mock_yf.Ticker.return_value = mock_ticker

        # Act
        result = self.gateway.fetch_ohlcv('USDJPY', 'H1')

        # Assert
        assert not result.empty
        # H1のデフォルトは'2y'
        mock_ticker.history.assert_called_once()
        call_kwargs = mock_ticker.history.call_args[1]
        assert call_kwargs['period'] == '2y'

    # ========================================
    # 【リアルタイム価格】3テスト
    # ========================================

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_realtime_success(self, mock_yf):
        """
        リアルタイム価格取得 - 成功

        条件: 複数シンボル指定
        期待: 全シンボルの価格情報返却
        """
        # Arrange
        mock_ticker_usdjpy = Mock()
        mock_ticker_usdjpy.info = {
            'regularMarketPrice': 150.50,
            'bid': 150.48,
            'ask': 150.52,
            'regularMarketChange': 0.30,
            'regularMarketChangePercent': 0.20,
            'regularMarketVolume': 100000
        }

        mock_ticker_eurusd = Mock()
        mock_ticker_eurusd.info = {
            'regularMarketPrice': 1.0850,
            'bid': 1.0848,
            'ask': 1.0852
        }

        mock_tickers = Mock()
        mock_tickers.tickers = {
            'USDJPY=X': mock_ticker_usdjpy,
            'EURUSD=X': mock_ticker_eurusd
        }
        mock_yf.Tickers.return_value = mock_tickers

        # Act
        result = self.gateway.fetch_realtime(['USDJPY', 'EURUSD'])

        # Assert
        assert 'USDJPY' in result
        assert 'EURUSD' in result
        assert result['USDJPY']['price'] == 150.50
        assert result['USDJPY']['bid'] == 150.48
        assert result['USDJPY']['ask'] == 150.52
        assert result['USDJPY']['spread'] == pytest.approx(0.04)
        assert result['EURUSD']['price'] == 1.0850

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_realtime_partial_error(self, mock_yf):
        """
        リアルタイム価格取得 - 一部シンボルエラー

        条件: 一部のシンボルで例外発生
        期待: 成功分は返却、エラー分はerror情報
        """
        # Arrange
        mock_ticker_usdjpy = Mock()
        mock_ticker_usdjpy.info = {'regularMarketPrice': 150.50, 'bid': 150.48, 'ask': 150.52}

        mock_ticker_invalid = Mock()
        mock_ticker_invalid.info.side_effect = Exception("Invalid ticker")

        mock_tickers = Mock()
        mock_tickers.tickers = {
            'USDJPY=X': mock_ticker_usdjpy,
            'INVALID=X': mock_ticker_invalid
        }
        mock_yf.Tickers.return_value = mock_tickers

        # Act
        result = self.gateway.fetch_realtime(['USDJPY', 'INVALID'])

        # Assert
        assert 'USDJPY' in result
        assert 'INVALID' in result
        assert result['USDJPY']['price'] == 150.50
        assert 'error' in result['INVALID']

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_latest_price_success(self, mock_yf):
        """
        最新価格取得 - 成功

        条件: 有効なシンボル
        期待: 価格のみ返却
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.info = {'regularMarketPrice': 150.50, 'bid': 150.48, 'ask': 150.52}

        mock_tickers = Mock()
        mock_tickers.tickers = {'USDJPY=X': mock_ticker}
        mock_yf.Tickers.return_value = mock_tickers

        # Act
        price = self.gateway.fetch_latest_price('USDJPY')

        # Assert
        assert price == 150.50

    # ========================================
    # 【キャッシュ管理】3テスト
    # ========================================

    def test_is_cache_valid_fresh(self):
        """
        キャッシュ検証 - 有効

        条件: キャッシュが有効期限内
        期待: True返却
        """
        # Arrange
        cache_key = 'test_key'
        self.gateway._cache[cache_key] = pd.DataFrame()
        self.gateway._cache_timestamps[cache_key] = time.time()

        # Act
        is_valid = self.gateway._is_cache_valid(cache_key)

        # Assert
        assert is_valid is True

    def test_is_cache_valid_expired(self):
        """
        キャッシュ検証 - 期限切れ

        条件: キャッシュが有効期限超過
        期待: False返却
        """
        # Arrange
        cache_key = 'test_key'
        self.gateway._cache[cache_key] = pd.DataFrame()
        self.gateway._cache_timestamps[cache_key] = time.time() - 120  # 2分前

        # Act
        is_valid = self.gateway._is_cache_valid(cache_key)

        # Assert
        assert is_valid is False

    def test_clear_cache(self):
        """
        キャッシュクリア

        条件: キャッシュにデータが存在
        期待: 全キャッシュクリア
        """
        # Arrange
        self.gateway._cache['key1'] = pd.DataFrame()
        self.gateway._cache['key2'] = pd.DataFrame()
        self.gateway._cache_timestamps['key1'] = time.time()
        self.gateway._cache_timestamps['key2'] = time.time()

        # Act
        self.gateway.clear_cache()

        # Assert
        assert len(self.gateway._cache) == 0
        assert len(self.gateway._cache_timestamps) == 0

    # ========================================
    # 【シンボル管理】3テスト
    # ========================================

    def test_get_supported_symbols(self):
        """
        サポートシンボル取得

        条件: なし
        期待: FOREX_SYMBOLSの全キー返却
        """
        # Act
        symbols = self.gateway.get_supported_symbols()

        # Assert
        assert 'USDJPY' in symbols
        assert 'EURUSD' in symbols
        assert 'GBPUSD' in symbols
        assert len(symbols) > 0

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_validate_symbol_known(self, mock_yf):
        """
        シンボル検証 - 既知のシンボル

        条件: FOREX_SYMBOLSに存在
        期待: True返却
        """
        # Act
        is_valid = self.gateway.validate_symbol('USDJPY')

        # Assert
        assert is_valid is True

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_validate_symbol_unknown(self, mock_yf):
        """
        シンボル検証 - 未知のシンボル

        条件: FOREX_SYMBOLSに存在しない、yfinanceでも無効
        期待: False返却
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.info = {}  # regularMarketPriceなし
        mock_yf.Ticker.return_value = mock_ticker

        # Act
        is_valid = self.gateway.validate_symbol('INVALID')

        # Assert
        assert is_valid is False

    # ========================================
    # 【複数時間枠取得】2テスト
    # ========================================

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_multiple_timeframes_success(self, mock_yf):
        """
        複数時間枠取得 - 成功

        条件: 複数の時間枠指定
        期待: 各時間枠のDataFrame返却
        """
        # Arrange
        mock_ticker = Mock()
        mock_ticker.history.return_value = self.test_ohlcv_df.copy()
        mock_yf.Ticker.return_value = mock_ticker

        # Act
        result = self.gateway.fetch_multiple_timeframes('USDJPY', ['M5', 'H1', 'D1'], period='1mo')

        # Assert
        assert 'M5' in result
        assert 'H1' in result
        assert 'D1' in result
        assert len(result['M5']) > 0
        assert len(result['H1']) > 0
        assert len(result['D1']) > 0

    @patch('src.infrastructure.gateways.market_data.yfinance_gateway.yf')
    def test_fetch_multiple_timeframes_partial_failure(self, mock_yf):
        """
        複数時間枠取得 - 一部失敗

        条件: 一部の時間枠で空DataFrame返却
        期待: 成功分のみ含まれる
        """
        # Arrange
        mock_ticker = Mock()
        # 最初は成功、次は空DataFrame
        mock_ticker.history.side_effect = [
            self.test_ohlcv_df.copy(),
            pd.DataFrame(),
            self.test_ohlcv_df.copy()
        ]
        mock_yf.Ticker.return_value = mock_ticker

        # Act
        result = self.gateway.fetch_multiple_timeframes('USDJPY', ['M5', 'H1', 'D1'], period='1mo')

        # Assert
        assert 'M5' in result
        assert 'H1' not in result  # 空だったので含まれない
        assert 'D1' in result


# テスト実行
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
