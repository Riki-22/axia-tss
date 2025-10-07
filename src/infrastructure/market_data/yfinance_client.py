# src/infrastructure/market_data/yfinance_client.py

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class YFinanceClient:
    """
    Yahoo Finance APIを使用した市場データ取得クライアント
    FX向けに最適化、キャッシュ機能付き
    """
    
    # FXシンボルのマッピング（Yahoo Finance形式）
    FOREX_SYMBOLS = {
        'USDJPY': 'USDJPY=X',
        'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X',
        'EURUSD': 'EURUSD=X',
        'GBPUSD': 'GBPUSD=X',
        'AUDJPY': 'AUDJPY=X',
        'NZDJPY': 'NZDJPY=X',
        'CADJPY': 'CADJPY=X',
        'CHFJPY': 'CHFJPY=X',
        'AUDUSD': 'AUDUSD=X',
        'NZDUSD': 'NZDUSD=X',
        'USDCAD': 'USDCAD=X',
        'USDCHF': 'USDCHF=X',
        'EURGBP': 'EURGBP=X'
    }
    
    # 時間枠のマッピング（MT5形式 → yfinance形式）
    TIMEFRAME_MAP = {
        'M1': '1m',
        'M5': '5m',
        'M15': '15m',
        'M30': '30m',
        'H1': '1h',
        'H4': '1h',  # yfinanceは4時間足非対応なので1時間足で代替
        'D1': '1d',
        'W1': '1wk',
        'MN1': '1mo'
    }
    
    # 期間のマッピング（データ量に応じた最適な期間）
    PERIOD_MAP = {
        '1m': '7d',    # 1分足は7日分
        '5m': '60d',   # 5分足は60日分
        '15m': '60d',
        '30m': '60d',
        '1h': '2y',    # 1時間足は2年分
        '1d': '10y',   # 日足は10年分
        '1wk': '10y',
        '1mo': '10y'
    }
    
    def __init__(self, cache_duration: int = 60):
        """
        Args:
            cache_duration: キャッシュの有効期限（秒）
        """
        self.cache_duration = cache_duration
        self._cache = {}
        self._cache_timestamps = {}
        
    def _get_yf_symbol(self, symbol: str) -> str:
        """内部シンボルをYahoo Finance形式に変換"""
        return self.FOREX_SYMBOLS.get(symbol, symbol)
    
    def _to_standard_ohlcv_format(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        yfinanceのデータを標準OHLCV形式に変換
        
        標準OHLCV形式:
        - timestamp_utc: datetime (index)
        - open: float
        - high: float
        - low: float
        - close: float
        - volume: int
        """
        if df.empty:
            return df
            
        # カラム名を統一
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # 必要なカラムを選択
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in required_cols if col in df.columns]
        df = df[available_cols]
        
        # Volumeが存在しない場合（FXの場合よくある）
        if 'volume' not in df.columns:
            df['volume'] = 0
        
        # データ型の確認と変換
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype('float64')
        df['volume'] = df['volume'].fillna(0).astype('int64')
        
        # シンボル情報を追加（メタデータとして）
        df.attrs['symbol'] = symbol
        df.attrs['source'] = 'yfinance'
        df.attrs['fetch_time'] = datetime.now()
        
        return df
    
    def fetch_ohlcv(self, 
                    symbol: str, 
                    timeframe: str = 'H1',
                    period: Optional[str] = None,
                    start: Optional[datetime] = None,
                    end: Optional[datetime] = None) -> pd.DataFrame:
        """
        OHLCVデータを取得
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
            timeframe: 時間枠（'M1', 'M5', 'H1', 'D1'など）
            period: 期間指定（'1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'）
            start: 開始日時（periodと排他）
            end: 終了日時（periodと排他）
            
        Returns:
            pd.DataFrame: Golden Schema形式のOHLCVデータ
        """
        try:
            yf_symbol = self._get_yf_symbol(symbol)
            interval = self.TIMEFRAME_MAP.get(timeframe, '1h')
            
            # キャッシュチェック
            cache_key = f"{symbol}_{timeframe}_{period}_{start}_{end}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"キャッシュヒット: {cache_key}")
                return self._cache[cache_key]
            
            # periodが指定されていない場合はデフォルト値を使用
            if period is None and start is None:
                period = self.PERIOD_MAP.get(interval, '1mo')
            
            logger.info(f"yfinanceからデータ取得: {symbol} {timeframe} period={period}")
            
            # データ取得
            ticker = yf.Ticker(yf_symbol)
            
            if start is not None or end is not None:
                df = ticker.history(
                    start=start,
                    end=end,
                    interval=interval,
                    auto_adjust=True,
                    prepost=True
                )
            else:
                df = ticker.history(
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                    prepost=True
                )
            
            # 標準OHLCV形式に変換
            df = self._to_standard_ohlcv_format(df, symbol)
            
            # キャッシュ保存
            self._cache[cache_key] = df
            self._cache_timestamps[cache_key] = time.time()
            
            logger.info(f"データ取得成功: {len(df)}件")
            return df
            
        except Exception as e:
            logger.error(f"yfinanceデータ取得エラー: {symbol} - {e}")
            return pd.DataFrame()
    
    def fetch_realtime(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        リアルタイム価格を取得（複数シンボル対応）
        
        Args:
            symbols: 通貨ペアのリスト
            
        Returns:
            Dict: {symbol: {price, bid, ask, timestamp}}
        """
        result = {}
        
        try:
            # Yahoo Finance形式に変換
            yf_symbols = [self._get_yf_symbol(s) for s in symbols]
            
            # 一括取得（効率的）
            tickers = yf.Tickers(' '.join(yf_symbols))
            
            for symbol, yf_symbol in zip(symbols, yf_symbols):
                try:
                    ticker = tickers.tickers[yf_symbol]
                    info = ticker.info
                    
                    # 価格情報を取得
                    result[symbol] = {
                        'price': info.get('regularMarketPrice', 0),
                        'bid': info.get('bid', 0),
                        'ask': info.get('ask', 0),
                        'spread': info.get('ask', 0) - info.get('bid', 0) if info.get('ask') and info.get('bid') else 0,
                        'change': info.get('regularMarketChange', 0),
                        'change_percent': info.get('regularMarketChangePercent', 0),
                        'volume': info.get('regularMarketVolume', 0),
                        'timestamp': datetime.now()
                    }
                    
                except Exception as e:
                    logger.warning(f"個別シンボルエラー: {symbol} - {e}")
                    result[symbol] = {
                        'price': 0,
                        'error': str(e),
                        'timestamp': datetime.now()
                    }
                    
        except Exception as e:
            logger.error(f"リアルタイムデータ取得エラー: {e}")
            
        return result
    
    def fetch_latest_price(self, symbol: str) -> Optional[float]:
        """
        最新価格を取得（シンプル版）
        
        Args:
            symbol: 通貨ペア
            
        Returns:
            float: 最新価格（エラー時はNone）
        """
        data = self.fetch_realtime([symbol])
        if symbol in data and 'price' in data[symbol]:
            return data[symbol]['price']
        return None
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """キャッシュの有効性をチェック"""
        if cache_key not in self._cache:
            return False
        
        timestamp = self._cache_timestamps.get(cache_key, 0)
        return (time.time() - timestamp) < self.cache_duration
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("キャッシュをクリアしました")
    
    def get_supported_symbols(self) -> List[str]:
        """サポートされているシンボルのリストを返す"""
        return list(self.FOREX_SYMBOLS.keys())
    
    def validate_symbol(self, symbol: str) -> bool:
        """シンボルが有効かチェック"""
        if symbol in self.FOREX_SYMBOLS:
            return True
        
        # Yahoo Financeで直接チェック
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return 'regularMarketPrice' in info
        except:
            return False
    
    def fetch_multiple_timeframes(self,
                                 symbol: str,
                                 timeframes: List[str],
                                 period: str = '1mo') -> Dict[str, pd.DataFrame]:
        """
        複数の時間枠のデータを一度に取得
        
        Args:
            symbol: 通貨ペア
            timeframes: 時間枠のリスト
            period: 取得期間
            
        Returns:
            Dict: {timeframe: DataFrame}
        """
        result = {}
        
        for tf in timeframes:
            df = self.fetch_ohlcv(symbol, tf, period=period)
            if not df.empty:
                result[tf] = df
            else:
                logger.warning(f"データ取得失敗: {symbol} {tf}")
                
        return result


# 使用例
if __name__ == "__main__":
    # ロギング設定
    logging.basicConfig(level=logging.INFO)
    
    # クライアント初期化
    client = YFinanceClient(cache_duration=60)
    
    # OHLCVデータ取得
    df = client.fetch_ohlcv('USDJPY', 'H1', period='1mo')
    print(f"取得データ数: {len(df)}")
    print(df.head())
    
    # リアルタイム価格取得
    prices = client.fetch_realtime(['USDJPY', 'EURUSD'])
    for symbol, data in prices.items():
        print(f"{symbol}: {data.get('price', 'N/A')}")
    
    # 複数時間枠取得
    multi_tf = client.fetch_multiple_timeframes('USDJPY', ['M5', 'H1', 'D1'])
    for tf, df in multi_tf.items():
        print(f"{tf}: {len(df)}件")