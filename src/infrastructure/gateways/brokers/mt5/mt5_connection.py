# src/infrastructure/gateways/brokers/mt5/mt5_connection.py
import MetaTrader5 as mt5
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class MT5Connection:
    """MT5接続管理クラス"""
    
    def __init__(self, credentials: Dict[str, Any], terminal_path: Optional[str] = None):
        self.credentials = credentials
        self.terminal_path = terminal_path
        self._connected = False
    
    def connect(self) -> bool:
        """MT5への接続"""
        if not self.credentials:
            logger.error("MT5接続試行前に認証情報がありません。")
            return False
            
        login_id = self.credentials.get('mt5_login')
        password = self.credentials.get('mt5_password')
        server = self.credentials.get('mt5_server')
        
        try:
            login_id = int(login_id)
        except (ValueError, TypeError):
            logger.error(f"mt5_loginが有効な数値ではありません: {login_id}")
            return False
        
        if not login_id or not password or not server:
            logger.error("MT5接続に必要な認証情報が不足しています。")
            return False
        
        if not self.terminal_path:
            logger.error("MT5_TERMINAL_PATH が設定されていません。")
            return False
        
        logger.info(f"MT5に接続試行... Login: {login_id}, Server: {server}, Path: {self.terminal_path}")
        
        if not mt5.initialize(login=login_id, password=password, server=server, 
                            timeout=10000, path=self.terminal_path):
            error_code = mt5.last_error()
            logger.error(f"MT5 initialize() 失敗: code={error_code[0]}, 説明={error_code[1]}")
            mt5.shutdown()
            return False
        else:
            logger.info("MT5 initialize() 成功。")
            terminal_info = mt5.terminal_info()
            if terminal_info:
                logger.info(f"接続先ターミナル: {terminal_info.name}, Build: {terminal_info.build}")
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"口座情報: Login={account_info.login}, Balance={account_info.balance:.2f}")
            self._connected = True
            return True
    
    def disconnect(self):
        """MT5から切断"""
        try:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5切断完了")
        except Exception as e:
            logger.error(f"MT5切断エラー: {e}")
    
    def is_connected(self) -> bool:
        """接続状態確認"""
        if not self._connected:
            return False
        terminal_info = mt5.terminal_info()
        return terminal_info is not None and terminal_info.connected
    
    def ensure_connected(self) -> bool:
        """接続を確保（必要なら再接続）"""
        if not self.is_connected():
            logger.info("MT5再接続を試みます...")
            return self.connect()
        return True