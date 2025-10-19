# src/infrastructure/gateways/brokers/mt5/mt5_account_provider.py
"""MT5口座情報プロバイダー

MetaTrader 5プラットフォームから口座情報を取得・提供するプロバイダー

命名規則:
    - Suffix: Provider
    - 理由: 口座情報提供の責務を持つ
    - パターン: MT5PriceProviderと一貫性

特徴:
    - 口座残高・証拠金情報取得
    - 本日損益計算（NYクローズ基準）
    - 証拠金率計算

依存関係:
    - MetaTrader5: MT5 Pythonライブラリ
    - MT5Connection: MT5接続管理クラス

使用例:
    >>> from src.infrastructure.di.container import container
    >>> 
    >>> account_provider = container.get_mt5_account_provider()
    >>> 
    >>> # 口座情報取得
    >>> account_info = account_provider.get_account_info()
    >>> if account_info:
    ...     print(f"Balance: {account_info['balance']}")
    >>> 
    >>> # 本日損益取得
    >>> today_pl = account_provider.calculate_today_pl()
    >>> if today_pl:
    ...     print(f"Today P/L: {today_pl['amount']}")
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

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

import pytz

logger = logging.getLogger(__name__)


class MT5AccountProvider:
    """
    MT5口座情報プロバイダー
    
    MetaTrader 5プラットフォームから口座情報を提供
    
    命名規則:
        - クラス名: MT5AccountProvider
        - Suffix: Provider（データ提供の責務）
        - 既存パターン: MT5PriceProvider, OhlcvDataProviderと同じ
    
    Attributes:
        connection (MT5Connection): MT5接続管理インスタンス
    
    Note:
        - Infrastructure層のプロバイダーパターン
        - NYクローズ基準で"本日"を判定
        - エラー時はNoneを返却
        - MT5DataCollectorと同様のエラーハンドリング
    """
    
    def __init__(self, connection: 'MT5Connection'):
        """
        初期化
        
        Args:
            connection: MT5接続管理インスタンス
        
        Example:
            >>> from src.infrastructure.di.container import container
            >>> provider = MT5AccountProvider(
            ...     connection=container.get_mt5_connection()
            ... )
        """
        self.connection = connection
        logger.info("MT5AccountProvider initialized")
    
    def get_account_info(self) -> Optional[Dict]:
        """
        口座情報を取得
        
        MT5から口座の残高、証拠金、含み損益等の情報を取得し、辞書形式で返却する
        
        Returns:
            dict: {
                'balance': float,          # 残高
                'equity': float,           # 有効証拠金
                'margin': float,           # 使用証拠金
                'free_margin': float,      # 余剰証拠金
                'margin_level': float,     # 証拠金率（%）
                'profit': float,           # 含み損益
                'currency': str,           # 通貨
                'leverage': int            # レバレッジ
            }
            None: 取得失敗時
        
        処理フロー:
            1. MT5接続状態確認
            2. account_info()で口座情報取得
            3. 証拠金率計算: (equity / margin) * 100
            4. 辞書形式で返却
        
        Example:
            >>> account = provider.get_account_info()
            >>> if account:
            ...     print(f"Balance: ¥{account['balance']:,.0f}")
            ...     print(f"Margin Level: {account['margin_level']:.0f}%")
        
        Note:
            - エラー時はログ記録してNoneを返す
            - MT5OrderExecutorのパターンを踏襲
        
        Raises:
            なし: 全てのエラーはログ記録してNoneを返す
        """
        logger.info("MT5から口座情報を取得します")
        
        try:
            # 1. 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # 2. 口座情報取得
            account = mt5.account_info()
            if account is None:
                logger.error("口座情報を取得できませんでした")
                return None
            
            # 3. 証拠金率計算（%）
            if account.margin > 0:
                margin_level = (account.equity / account.margin) * 100
            else:
                # margin=0の場合
                # equity=0なら0%, equity>0なら無限大
                margin_level = 0.0 if account.equity == 0 else float('inf')
            
            # 4. 辞書化
            result = {
                'balance': account.balance,
                'equity': account.equity,
                'margin': account.margin,
                'free_margin': account.margin_free,
                'margin_level': margin_level,
                'profit': account.profit,
                'currency': account.currency,
                'leverage': account.leverage
            }
            
            logger.info(
                f"口座情報を取得しました: "
                f"Balance={account.balance:.2f}, "
                f"Equity={account.equity:.2f}, "
                f"Margin Level={margin_level:.0f}%"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"口座情報取得中にエラー: {e}",
                exc_info=True
            )
            return None
    
    def get_balance(self) -> Optional[float]:
        """
        残高を取得
        
        get_account_info()の簡易版として、残高のみを返却する
        
        Returns:
            float: 残高
            None: 取得失敗時
        
        Example:
            >>> balance = provider.get_balance()
            >>> if balance:
            ...     print(f"Balance: ¥{balance:,.0f}")
        """
        account = self.get_account_info()
        return account['balance'] if account else None
    
    def get_margin_info(self) -> Optional[Dict]:
        """
        証拠金情報を取得
        
        Args:
            なし
        
        Returns:
            dict: {
                'margin': float,         # 使用証拠金
                'free_margin': float,    # 余剰証拠金
                'margin_level': float    # 証拠金率（%）
            }
            None: 取得失敗時
        
        Example:
            >>> margin_info = provider.get_margin_info()
            >>> if margin_info:
            ...     print(f"Margin Level: {margin_info['margin_level']:.0f}%")
        """
        account = self.get_account_info()
        if account:
            return {
                'margin': account['margin'],
                'free_margin': account['free_margin'],
                'margin_level': account['margin_level']
            }
        return None
    
    def calculate_today_pl(self) -> Optional[Dict]:
        """
        本日の損益を計算（NYクローズ基準）
        
        NYクローズ（夏時間 UTC 21:00 / 冬時間 UTC 22:00）を"本日"の開始として、
        実現損益 + 含み損益の合計を計算して返却する
        
        Returns:
            dict: {
                'amount': float,      # 損益金額
                'percentage': float   # 損益率（%）
            }
            None: 取得失敗時
        
        処理フロー:
            1. 現在時刻取得（UTC）
            2. 夏時間/冬時間判定
            3. 本日のNYクローズ時刻計算
            4. history_deals_get()で取引履歴取得
            5. 実現損益 + 含み損益計算
            6. %計算
        
        Example:
            >>> today_pl = provider.calculate_today_pl()
            >>> if today_pl:
            ...     print(f"Today P/L: ¥{today_pl['amount']:+,.0f}")
            ...     print(f"Percentage: {today_pl['percentage']:+.2f}%")
        
        Note:
            - NYクローズ基準: 夏時間 21:00 UTC / 冬時間 22:00 UTC
            - 3-10月: 夏時間（簡易判定）
            - 11-2月: 冬時間
            - MT5DataCollectorと同様のエラーハンドリング
        
        Raises:
            なし: 全てのエラーはログ記録してNoneを返す
        """
        logger.info("本日の損益を計算します（NYクローズ基準）")
        
        try:
            # 1. 接続確認
            if not self.connection.ensure_connected():
                logger.error("MT5接続が確立されていません")
                return None
            
            # 2. 現在時刻（UTC）
            now = datetime.now(pytz.UTC)
            
            # 3. NYクローズ時刻判定（簡易版）
            # 夏時間（3月〜10月）: UTC 21:00
            # 冬時間（11月〜2月）: UTC 22:00
            if 3 <= now.month <= 10:
                ny_close_hour = 21  # 夏時間
            else:
                ny_close_hour = 22  # 冬時間
            
            # 4. 今日のNYクローズ時刻
            today_ny_close = now.replace(
                hour=ny_close_hour,
                minute=0,
                second=0,
                microsecond=0
            )
            
            # 5. 基準時刻決定
            # 現在時刻が今日のNYクローズ前なら、昨日のNYクローズが基準
            if now < today_ny_close:
                today_start = today_ny_close - timedelta(days=1)
            else:
                today_start = today_ny_close
            
            logger.info(
                f"本日の開始時刻（NYクローズ）: {today_start.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
            
            # 6. 取引履歴取得
            history = mt5.history_deals_get(today_start, now)
            
            if history is None:
                logger.warning("取引履歴を取得できませんでした")
                # 履歴なしの場合もデフォルト値を返す
                return {'amount': 0.0, 'percentage': 0.0}
            
            # 7. 実現損益計算
            # entry=1 は決済（out）
            realized_pl = sum(
                deal.profit for deal in history if deal.entry == 1
            )
            
            logger.debug(f"実現損益: ¥{realized_pl:+,.2f} ({len(history)}件の取引)")
            
            # 8. 含み損益取得
            account = self.get_account_info()
            if account:
                unrealized_pl = account['profit']
                total_pl = realized_pl + unrealized_pl
                
                # 9. %計算
                if account['balance'] > 0:
                    pl_percentage = (total_pl / account['balance']) * 100
                else:
                    pl_percentage = 0.0
                
                logger.info(
                    f"本日損益: 実現=¥{realized_pl:+,.2f}, "
                    f"含み=¥{unrealized_pl:+,.2f}, "
                    f"合計=¥{total_pl:+,.2f} ({pl_percentage:+.2f}%)"
                )
                
                return {
                    'amount': total_pl,
                    'percentage': pl_percentage
                }
            
            # account取得失敗の場合、実現損益のみ返す
            logger.warning("口座情報取得失敗のため、実現損益のみ返却します")
            return {'amount': realized_pl, 'percentage': 0.0}
            
        except Exception as e:
            logger.error(
                f"本日損益計算中にエラー: {e}",
                exc_info=True
            )
            return None