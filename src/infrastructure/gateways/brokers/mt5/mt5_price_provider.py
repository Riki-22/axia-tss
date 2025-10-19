# src/infrastructure/gateways/brokers/mt5/mt5_price_provider.py
"""MT5価格情報プロバイダー

MetaTrader 5プラットフォームからリアルタイム価格情報を取得・提供するプロバイダー

命名規則:
    - Suffix: Provider
    - 理由: リアルタイムデータ提供の責務を持つ
    - パターン: OhlcvDataProviderと一貫性

特徴:
    - リアルタイム価格取得（Bid/Ask）
    - シンボル情報取得
    - スプレッド計算（pips）
    - MT5接続状態の自動確認

依存関係:
    - MetaTrader5: MT5 Pythonライブラリ
    - MT5Connection: MT5接続管理クラス

使用例:
    >>> from src.infrastructure.di.container import container
    >>> 
    >>> price_provider = container.get_mt5_price_provider()
    >>> 
    >>> # 現在価格取得
    >>> price_info = price_provider.get_current_price('USDJPY')
    >>> if price_info:
    ...     print(f"Ask: {price_info['ask']}, Spread: {price_info['spread']:.1f} pips")
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

# MT5は条件付きインポート
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    # 警告は環境変数で制御
    import os
    if os.getenv('DEBUG', '').lower() == 'true':
        logging.warning("MetaTrader5 module not available. MT5 features will be disabled.")

logger = logging.getLogger(__name__)


class MT5PriceProvider:
    """
    MT5価格情報プロバイダー
    
    MetaTrader 5プラットフォームからリアルタイム価格情報を提供する
    
    命名規則:
        - クラス名: MT5PriceProvider
        - Suffix: Provider（データ提供の責務）
        - 既存パターン: OhlcvDataProvider, MT5DataCollectorと同じ
    
    Attributes:
        connection (MT5Connection): MT5接続管理インスタンス
    
    Note:
        - Infrastructure層のプロバイダーパターン
        - Application層から依存性注入で利用
        - エラー時はNoneを返却（上位層で判断）
        - MT5DataCollectorと同様のエラーハンドリング
    """
    
    def __init__(self, connection: 'MT5Connection'):
        """
        初期化
        
        Args:
            connection: MT5接続管理インスタンス
        
        Example:
            >>> from src.infrastructure.di.container import container
            >>> provider = MT5PriceProvider(
            ...     connection=container.get_mt5_connection()
            ... )
        """
        self.connection = connection
        logger.info("MT5PriceProvider initialized")
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """
        現在価格を取得
        
        MT5からリアルタイムのBid/Ask価格を取得し、スプレッドを計算する
        
        Args:
            symbol: 通貨ペア（例: "USDJPY", "EURUSD"）
        
        Returns:
            dict: {
                'symbol': str,           # 通貨ペア
                'bid': float,            # Bid価格
                'ask': float,            # Ask価格
                'spread': float,         # スプレッド（pips）
                'time': datetime         # 取得時刻（UTC）
            }
            None: 取得失敗時
        
        処理フロー:
            1. MT5接続状態確認
            2. symbol_info_tick()でTick情報取得
            3. symbol_info()でシンボル情報取得
            4. スプレッド計算（pips）
            5. 辞書形式で返却
        
        Example:
            >>> price_info = provider.get_current_price('USDJPY')
            >>> if price_info:
            ...     print(f"USDJPY Ask: {price_info['ask']}")
            ...     print(f"Spread: {price_info['spread']:.1f} pips")
        
        Note:
            - エラー時はログ記録してNoneを返す
            - MT5OrderExecutorと同様のパターン
        
        Raises:
            なし: 全てのエラーはログ記録してNoneを返す
        """
        logger.info(f"MT5から {symbol} の現在価格を取得します")
        
        try:
            # 1. 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # 2. Tick情報取得
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"{symbol} のTick情報を取得できませんでした")
                return None
            
            # 3. シンボル情報取得（スプレッド計算用）
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                point = symbol_info.point
                # スプレッド計算: (ask - bid) / point
                # 例: USDJPY point=0.001の場合、spread=0.030なら30pips
                spread_pips = (tick.ask - tick.bid) / point
            else:
                logger.debug(f"{symbol} のシンボル情報を取得できませんでした")
                spread_pips = 0.0
            
            # 4. 結果作成
            result = {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': spread_pips,
                'time': datetime.fromtimestamp(tick.time)
            }
            
            logger.info(
                f"{symbol} の現在価格を取得しました: "
                f"Bid={tick.bid:.5f}, Ask={tick.ask:.5f}, "
                f"Spread={spread_pips:.1f} pips"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"{symbol} の現在価格取得中にエラー: {e}",
                exc_info=True
            )
            return None
    
    def get_bid_ask(self, symbol: str) -> Optional[Tuple[float, float]]:
        """
        Bid/Ask価格を取得
        
        get_current_price()の簡易版として、Bid/Ask価格のみを
        タプルで返却する
        
        Args:
            symbol: 通貨ペア
        
        Returns:
            tuple: (bid, ask)
            None: 取得失敗時
        
        Example:
            >>> bid, ask = provider.get_bid_ask('USDJPY')
            >>> if bid and ask:
            ...     print(f"Bid: {bid}, Ask: {ask}")
        
        Note:
            - 内部的にget_current_price()を呼び出す
            - スプレッドが不要な場合に使用
        """
        price_info = self.get_current_price(symbol)
        if price_info:
            return (price_info['bid'], price_info['ask'])
        return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        シンボル情報を取得
        
        MT5からシンボルの詳細情報（桁数、ポイント値、ロットサイズ等）を取得する
        
        Args:
            symbol: 通貨ペア
        
        Returns:
            dict: {
                'symbol': str,                    # 通貨ペア
                'digits': int,                    # 小数点桁数
                'point': float,                   # 1ポイントの値
                'trade_contract_size': float,     # 1ロットのサイズ
                'volume_min': float,              # 最小ロット
                'volume_max': float,              # 最大ロット
                'volume_step': float              # ロットステップ
            }
            None: 取得失敗時
        
        処理フロー:
            1. MT5接続状態確認
            2. symbol_info()でシンボル情報取得
            3. 必要な属性を辞書化
        
        Example:
            >>> info = provider.get_symbol_info('USDJPY')
            >>> if info:
            ...     pip_value = info['point'] * 10  # 1pip = 10 points
            ...     print(f"1pip = {pip_value}")
        
        Note:
            - 注文計算（TP/SL価格計算）で使用
            - MT5DataCollectorのfetch_ohlcv_dataと同様のパターン
        
        Raises:
            なし: 全てのエラーはログ記録してNoneを返す
        """
        logger.info(f"MT5から {symbol} のシンボル情報を取得します")
        
        try:
            # 1. 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # 2. シンボル情報取得
            info = mt5.symbol_info(symbol)
            if info is None:
                logger.warning(f"{symbol} のシンボル情報を取得できませんでした")
                return None
            
            # 3. 辞書化
            result = {
                'symbol': symbol,
                'digits': info.digits,
                'point': info.point,
                'trade_contract_size': info.trade_contract_size,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step
            }
            
            logger.info(
                f"{symbol} のシンボル情報を取得しました: "
                f"digits={info.digits}, point={info.point}"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"{symbol} のシンボル情報取得中にエラー: {e}",
                exc_info=True
            )
            return None