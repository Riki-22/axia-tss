# src/infrastructure/gateways/brokers/mt5/mt5_position_provider.py

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# MT5は条件付きインポート
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    import os
    if os.getenv('DEBUG', '').lower() == 'true':
        logging.warning("MetaTrader5 module not available. MT5 features will be disabled.")

logger = logging.getLogger(__name__)


class MT5PositionProvider:
    """
    MT5ポジション情報プロバイダー
    
    責務:
    - MT5からリアルタイムポジション情報を取得
    - ポジション決済の実行
    - ポジション情報のフォーマット（UI表示用）
    
    設計方針:
    - MT5をSingle Source of Truth とする
    - DynamoDB記録は Phase 2で実装（現時点では記録しない）
    - 既存のMT5PriceProvider, MT5AccountProviderと同じパターン
    
    Usage:
        >>> provider = MT5PositionProvider(mt5_connection)
        >>> positions = provider.get_all_positions()
        >>> success = provider.close_position(12345678)
    """
    
    def __init__(self, connection: 'MT5Connection'):
        """
        初期化
        
        Args:
            connection: MT5接続管理インスタンス
        """
        self.connection = connection
        logger.info("MT5PositionProvider initialized")
    
    def get_all_positions(self) -> List[Dict]:
        """
        全オープンポジションを取得
        
        Returns:
            List[Dict]: [
                {
                    'ticket': int,           # MT5チケット番号
                    'symbol': str,           # 通貨ペア
                    'type': str,             # 'BUY' or 'SELL'
                    'volume': float,         # ロットサイズ
                    'price_open': float,     # エントリー価格
                    'price_current': float,  # 現在価格
                    'sl': float,             # ストップロス（0.0の場合は未設定）
                    'tp': float,             # テイクプロフィット（0.0の場合は未設定）
                    'profit': float,         # 含み損益（通貨単位）
                    'profit_pips': float,    # 含み損益（pips）
                    'swap': float,           # スワップ損益
                    'time': datetime,        # オープン時刻（UTC）
                    'magic': int,            # マジックナンバー
                    'comment': str           # コメント
                },
                ...
            ]
            
        Example:
            >>> provider = MT5PositionProvider(connection)
            >>> positions = provider.get_all_positions()
            >>> print(f"Open positions: {len(positions)}")
            >>> for pos in positions:
            ...     print(f"{pos['symbol']} {pos['type']} {pos['volume']} lot, P&L: ¥{pos['profit']:,.0f}")
        """
        try:
            if not self.connection.ensure_connected():
                logger.error("MT5 connection not available")
                return []
            
            # MT5から全ポジション取得
            positions = mt5.positions_get()
            
            if positions is None:
                logger.warning("No positions returned from MT5 (could be empty)")
                return []
            
            # 各ポジションをフォーマット
            formatted_positions = []
            for position in positions:
                formatted_pos = self._format_position(position)
                if formatted_pos:
                    formatted_positions.append(formatted_pos)
            
            logger.info(f"Retrieved {len(formatted_positions)} positions from MT5")
            return formatted_positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}", exc_info=True)
            return []
    
    def get_position_by_ticket(self, ticket: int) -> Optional[Dict]:
        """
        チケット番号でポジションを取得
        
        Args:
            ticket: MT5ポジションチケット番号
        
        Returns:
            Dict: ポジション情報（get_all_positions()と同じ形式）
            None: ポジションが見つからない場合
            
        Example:
            >>> position = provider.get_position_by_ticket(12345678)
            >>> if position:
            ...     print(f"Position: {position['symbol']} {position['profit']:+.2f}")
        """
        try:
            if not self.connection.ensure_connected():
                logger.error("MT5 connection not available")
                return None
            
            # 特定チケットのポジション取得
            positions = mt5.positions_get(ticket=ticket)
            
            if positions is None or len(positions) == 0:
                logger.warning(f"Position with ticket {ticket} not found")
                return None
            
            # 最初の（唯一の）ポジションをフォーマット
            return self._format_position(positions[0])
            
        except Exception as e:
            logger.error(f"Error getting position {ticket}: {e}", exc_info=True)
            return None
    
    def close_position(
        self, 
        ticket: int, 
        volume: Optional[float] = None,
        deviation: int = 20
    ) -> Tuple[bool, Optional[str]]:
        """
        ポジションを決済
        
        Args:
            ticket: MT5ポジションチケット番号
            volume: 決済ロット数（Noneの場合は全決済）
            deviation: 許容スリッページ（pips）
        
        Returns:
            Tuple[bool, Optional[str]]: (成功フラグ, エラーメッセージ)
            
        Example:
            >>> # 全決済
            >>> success, error = provider.close_position(12345678)
            >>> if success:
            ...     print("Position closed successfully")
            >>> 
            >>> # 部分決済
            >>> success, error = provider.close_position(12345678, volume=0.05)
        """
        try:
            # Kill Switch確認
            from src.infrastructure.di.container import container
            try:
                kill_switch_repo = container.get_kill_switch_repository()
                if kill_switch_repo.is_active():
                    error_msg = "Kill Switch is active - position close blocked"
                    logger.warning(error_msg)
                    return False, error_msg
            except Exception as e:
                logger.warning(f"Kill Switch check failed: {e}")
                # Kill Switch確認失敗は警告のみ（決済は継続）
            
            if not self.connection.ensure_connected():
                error_msg = "MT5 connection not available"
                logger.error(error_msg)
                return False, error_msg
            
            # ポジション情報取得
            position_info = self.get_position_by_ticket(ticket)
            if not position_info:
                error_msg = f"Position {ticket} not found"
                logger.error(error_msg)
                return False, error_msg
            
            # 決済ロット数決定
            close_volume = volume if volume is not None else position_info['volume']
            
            # 決済注文の方向とPrice決定
            if position_info['type'] == 'BUY':
                order_type = mt5.ORDER_TYPE_SELL
                symbol_info = mt5.symbol_info_tick(position_info['symbol'])
                price = symbol_info.bid if symbol_info else 0.0
            else:  # SELL
                order_type = mt5.ORDER_TYPE_BUY  
                symbol_info = mt5.symbol_info_tick(position_info['symbol'])
                price = symbol_info.ask if symbol_info else 0.0
            
            if price <= 0:
                error_msg = f"Invalid price for {position_info['symbol']}"
                logger.error(error_msg)
                return False, error_msg
            
            # 決済リクエスト作成
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': position_info['symbol'],
                'volume': close_volume,
                'type': order_type,
                'position': ticket,  # ポジションチケット指定
                'price': price,
                'deviation': deviation,
                'magic': position_info['magic'],
                'comment': f'Closed_by_AXIA_{int(datetime.now().timestamp())}',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC
            }
            
            logger.info(
                f"Closing position {ticket}: {position_info['symbol']} "
                f"{position_info['type']} {close_volume} lot @ {price:.5f}"
            )
            
            # 決済実行
            result = mt5.order_send(request)
            
            if result is None:
                error_msg = "MT5 order_send returned None"
                logger.error(error_msg)
                return False, error_msg
            
            # 結果確認
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(
                    f"Position {ticket} closed successfully: "
                    f"order={result.order}, price={result.price}, "
                    f"volume={result.volume}"
                )
                return True, None
                
            else:
                error_msg = (
                    f"Position close failed: retcode={result.retcode}, "
                    f"comment={result.comment}"
                )
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Exception during position close: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def calculate_total_unrealized_pnl(self) -> float:
        """
        全ポジションの含み損益合計を計算
        
        Returns:
            float: 総含み損益（通貨単位）
            
        Example:
            >>> total_pnl = provider.calculate_total_unrealized_pnl()
            >>> print(f"Total unrealized P&L: ¥{total_pnl:+,.0f}")
        """
        try:
            positions = self.get_all_positions()
            total_pnl = sum(pos['profit'] for pos in positions)
            
            logger.debug(f"Total unrealized P&L: {total_pnl:.2f} from {len(positions)} positions")
            return total_pnl
            
        except Exception as e:
            logger.error(f"Error calculating total P&L: {e}", exc_info=True)
            return 0.0
    
    def get_positions_by_symbol(self, symbol: str) -> List[Dict]:
        """
        特定シンボルのポジションを取得
        
        Args:
            symbol: 通貨ペア（例: 'USDJPY'）
        
        Returns:
            List[Dict]: 該当するポジションのリスト
            
        Example:
            >>> usdjpy_positions = provider.get_positions_by_symbol('USDJPY')
            >>> print(f"USDJPY positions: {len(usdjpy_positions)}")
        """
        try:
            all_positions = self.get_all_positions()
            symbol_positions = [
                pos for pos in all_positions 
                if pos['symbol'] == symbol
            ]
            
            logger.debug(f"Found {len(symbol_positions)} positions for {symbol}")
            return symbol_positions
            
        except Exception as e:
            logger.error(f"Error getting positions for {symbol}: {e}", exc_info=True)
            return []
    
    def _format_position(self, mt5_position) -> Optional[Dict]:
        """
        MT5ポジション情報をUI表示用フォーマットに変換
        
        Args:
            mt5_position: MT5のPositionInfoオブジェクト
        
        Returns:
            Dict: フォーマット済みポジション情報
            None: フォーマット失敗時
        """
        try:
            # 売買方向
            side = 'BUY' if mt5_position.type == mt5.ORDER_TYPE_BUY else 'SELL'
            
            # pips計算（通貨ペア別）
            symbol_info = mt5.symbol_info(mt5_position.symbol)
            if symbol_info:
                point = symbol_info.point
                # 1pip = 10 points (大部分の通貨ペア)
                pip_value = point * 10
            else:
                # フォールバック: JPYペアかどうかで判定
                pip_value = 0.01 if 'JPY' in mt5_position.symbol else 0.0001
            
            # pips損益計算
            if side == 'BUY':
                profit_pips = (mt5_position.price_current - mt5_position.price_open) / pip_value
            else:  # SELL
                profit_pips = (mt5_position.price_open - mt5_position.price_current) / pip_value
            
            return {
                'ticket': mt5_position.ticket,
                'symbol': mt5_position.symbol,
                'type': side,
                'volume': mt5_position.volume,
                'price_open': mt5_position.price_open,
                'price_current': mt5_position.price_current,
                'sl': mt5_position.sl,
                'tp': mt5_position.tp,
                'profit': mt5_position.profit,
                'profit_pips': profit_pips,
                'swap': mt5_position.swap,
                'time': datetime.fromtimestamp(mt5_position.time, tz=timezone.utc),
                'magic': mt5_position.magic,
                'comment': mt5_position.comment or ''
            }
            
        except Exception as e:
            logger.error(f"Error formatting position {mt5_position.ticket}: {e}", exc_info=True)
            return None