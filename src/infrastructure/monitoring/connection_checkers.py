# src/infrastructure/monitoring/connection_checkers.py

import time
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """サービス状態"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ConnectionStatus:
    """接続状態"""
    service_name: str
    status: ServiceStatus
    connected: bool
    last_check: datetime
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None

class DynamoDBConnectionChecker:
    """DynamoDB接続チェッカー"""
    
    def __init__(self, table_name: str, dynamodb_resource):
        self.table_name = table_name
        self.dynamodb_resource = dynamodb_resource
        self.table = dynamodb_resource.Table(table_name) if dynamodb_resource else None
    
    def check_connection(self) -> ConnectionStatus:
        """接続状態をチェック"""
        start_time = time.time()
        
        try:
            if not self.table:
                return ConnectionStatus(
                    service_name="dynamodb",
                    status=ServiceStatus.UNHEALTHY,
                    connected=False,
                    last_check=datetime.now(),
                    error="Table not initialized"
                )
            
            # テーブル状態チェック
            table_status = self.table.table_status
            latency = (time.time() - start_time) * 1000
            
            return ConnectionStatus(
                service_name="dynamodb",
                status=ServiceStatus.HEALTHY,
                connected=True,
                last_check=datetime.now(),
                latency_ms=latency,
                metadata={
                    'table_name': self.table_name,
                    'table_status': table_status
                }
            )
            
        except Exception as e:
            return ConnectionStatus(
                service_name="dynamodb",
                status=ServiceStatus.UNHEALTHY,
                connected=False,
                last_check=datetime.now(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )