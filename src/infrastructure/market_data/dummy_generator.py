# src/infrastructure/market_data/dummy_generator.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DummyMarketDataGenerator:
    """ダミーの市場データを生成するクラス"""
    
    def __init__(self, seed: Optional[int] = 42):
        """
        Args:
            seed: 乱数シード（再現性のため）
        """
        self.seed = seed
        
    def generate_ohlcv(self, 
                      days: int = 30,
                      timeframe: str = 'H1',
                      base_price: float = 150.0,
                      volatility: float = 0.5,
                      trend: float = 0.0) -> pd.DataFrame:
        """
        ダミーのOHLCVデータを生成
        
        Args:
            days: 生成する日数
            timeframe: 時間枠（'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'）
            base_price: 基準価格
            volatility: ボラティリティ（価格変動の大きさ）
            trend: トレンド（正：上昇、負：下降、0：レンジ）
        
        Returns:
            pd.DataFrame: 標準OHLCV形式のダミーデータ
        """
        # 時間枠に応じた期間数を計算
        periods_per_day = self._get_periods_per_day(timeframe)
        total_periods = days * periods_per_day
        
        # 時間枠に応じた頻度を取得
        freq = self._get_frequency(timeframe)
        
        # タイムスタンプ生成
        dates = pd.date_range(
            end=datetime.now(),
            periods=total_periods,
            freq=freq
        )
        
        # ランダムウォーク価格生成
        np.random.seed(self.seed)
        prices = self._generate_random_walk(
            total_periods=total_periods,
            base_price=base_price,
            volatility=volatility,
            trend=trend
        )
        
        # OHLCデータ生成
        df = self._create_ohlc_from_prices(prices, dates)
        
        # Volume生成（リアルなパターンをシミュレート）
        df['volume'] = self._generate_volume(total_periods, base_volume=5000)
        
        # 論理的整合性の確保
        df = self._ensure_ohlc_consistency(df)
        
        # メタデータ追加
        df.attrs['symbol'] = 'DUMMY'
        df.attrs['source'] = 'dummy_generator'
        df.attrs['timeframe'] = timeframe
        df.attrs['fetch_time'] = datetime.now()
        
        logger.info(f"Generated dummy data: {timeframe} x {total_periods} periods")
        
        return df
    
    def _get_periods_per_day(self, timeframe: str) -> int:
        """時間枠ごとの1日あたりの期間数"""
        mapping = {
            'M1': 1440,  # 60 * 24
            'M5': 288,   # 12 * 24
            'M15': 96,   # 4 * 24
            'M30': 48,   # 2 * 24
            'H1': 24,
            'H4': 6,
            'D1': 1
        }
        return mapping.get(timeframe, 24)
    
    def _get_frequency(self, timeframe: str) -> str:
        """pandas用の頻度文字列を取得"""
        mapping = {
            'M1': '1min',
            'M5': '5min',
            'M15': '15min',
            'M30': '30min',
            'H1': '1h',
            'H4': '4h',
            'D1': '1D'
        }
        return mapping.get(timeframe, '1h')
    
    def _generate_random_walk(self, 
                             total_periods: int,
                             base_price: float,
                             volatility: float,
                             trend: float) -> np.ndarray:
        """ランダムウォークで価格系列を生成"""
        prices = []
        price = base_price
        
        for i in range(total_periods):
            # トレンド成分 + ランダム成分
            change = trend * 0.01 + np.random.randn() * volatility
            price += change
            
            # 価格が負にならないよう制限
            price = max(price, base_price * 0.5)
            prices.append(price)
            
        return np.array(prices)
    
    def _create_ohlc_from_prices(self, 
                                prices: np.ndarray,
                                dates: pd.DatetimeIndex) -> pd.DataFrame:
        """価格系列からOHLCデータを作成"""
        # ベースとなるclose価格
        close_prices = prices
        
        # Open: 前期間のClose + 小さなギャップ
        gaps = np.random.randn(len(prices)) * 0.1
        open_prices = np.roll(close_prices, 1) + gaps
        open_prices[0] = close_prices[0]  # 最初の値は同じ
        
        # High: 期間中の最高値
        high_variation = np.abs(np.random.randn(len(prices)) * 0.3)
        high_prices = np.maximum(open_prices, close_prices) + high_variation
        
        # Low: 期間中の最安値
        low_variation = np.abs(np.random.randn(len(prices)) * 0.3)
        low_prices = np.minimum(open_prices, close_prices) - low_variation
        
        return pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices
        }, index=dates)
    
    def _generate_volume(self, 
                        total_periods: int,
                        base_volume: int = 5000) -> np.ndarray:
        """リアルなボリュームパターンを生成"""
        # 基本ボリューム + ランダム変動
        volume = np.random.randint(
            int(base_volume * 0.2), 
            int(base_volume * 2), 
            total_periods
        )
        
        # 時々スパイク（大量取引）を追加
        spike_indices = np.random.choice(
            total_periods, 
            size=int(total_periods * 0.05),  # 5%の確率
            replace=False
        )
        volume[spike_indices] = (volume[spike_indices] * np.random.uniform(2, 5, len(spike_indices))).astype(int)
        
        return volume
    
    def _ensure_ohlc_consistency(self, df: pd.DataFrame) -> pd.DataFrame:
        """OHLCデータの論理的整合性を確保"""
        # High は Open, Close, Low より大きい
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        
        # Low は Open, Close, High より小さい
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
        
        return df
    
    def generate_with_pattern(self,
                            days: int = 30,
                            timeframe: str = 'H1',
                            pattern: str = 'trend_up') -> pd.DataFrame:
        """
        特定のパターンを持つダミーデータを生成
        
        Args:
            days: 生成日数
            timeframe: 時間枠
            pattern: パターンタイプ
                - 'trend_up': 上昇トレンド
                - 'trend_down': 下降トレンド
                - 'range': レンジ相場
                - 'volatile': 高ボラティリティ
        
        Returns:
            pd.DataFrame: パターンを含むOHLCVデータ
        """
        patterns = {
            'trend_up': {'trend': 0.5, 'volatility': 0.3},
            'trend_down': {'trend': -0.5, 'volatility': 0.3},
            'range': {'trend': 0.0, 'volatility': 0.2},
            'volatile': {'trend': 0.0, 'volatility': 1.0}
        }
        
        params = patterns.get(pattern, patterns['range'])
        
        return self.generate_ohlcv(
            days=days,
            timeframe=timeframe,
            base_price=150.0,
            **params
        )