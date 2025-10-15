# 拡張可能なシステムステータス管理設計

**作成日**: 2025-10-12  
**目的**: MT5や他のサービスの接続状態も統合管理できる設計

---

## 🎯 設計方針

### 現在の要件
- Kill Switch状態
- DynamoDB接続状態

### 将来の要件
- **MT5接続状態**（接続中/切断/再接続中）
- **Redis接続状態**（Phase 2）
- **SQS Queue状態**（メッセージ数、DLQ状態）
- **S3アクセス状態**
- **外部API状態**（yfinance等）

---

## 📐 拡張可能な設計

### 1. Domain層: 汎用的なステータスモデル

**ファイル**: `src/domain/entities/system_status.py`

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

class ServiceStatus(Enum):
    """サービス状態の列挙型"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ConnectionStatus:
    """汎用的な接続状態"""
    service_name: str
    status: ServiceStatus
    connected: bool
    last_check: datetime
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return {
            'service_name': self.service_name,
            'status': self.status.value,
            'connected': self.connected,
            'last_check': self.last_check.isoformat(),
            'latency_ms': self.latency_ms,
            'error': self.error,
            'metadata': self.metadata or {}
        }

@dataclass
class SystemHealth:
    """システム全体のヘルス状態"""
    overall_status: ServiceStatus
    kill_switch: Dict[str, Any]
    connections: Dict[str, ConnectionStatus]
    timestamp: datetime
    
    @property
    def is_tradeable(self) -> bool:
        """取引可能な状態かチェック"""
        # Kill Switchがオフ かつ 必須サービスが正常
        if self.kill_switch.get('active', True):
            return False
        
        # 必須サービスのチェック
        required_services = ['dynamodb', 'mt5']
        for service in required_services:
            if service in self.connections:
                if not self.connections[service].connected:
                    return False
        
        return True
```

### 2. Domain層: 接続チェッカーインターフェース

**ファイル**: `src/domain/repositories/connection_checker.py`

```python
from abc import ABC, abstractmethod
from src.domain.entities.system_status import ConnectionStatus

class IConnectionChecker(ABC):
    """接続チェッカーの共通インターフェース"""
    
    @abstractmethod
    def check_connection(self) -> ConnectionStatus:
        """接続状態をチェック"""
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """サービス名を取得"""
        pass
```

### 3. Infrastructure層: 各サービスのチェッカー実装

**ファイル**: `src/infrastructure/monitoring/connection_checkers.py`

```python
import time
from datetime import datetime
from typing import Optional
import logging

from src.domain.repositories.connection_checker import IConnectionChecker
from src.domain.entities.system_status import ConnectionStatus, ServiceStatus
from infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

class DynamoDBConnectionChecker(IConnectionChecker):
    """DynamoDB接続チェッカー"""
    
    def __init__(self):
        self.table_name = settings.DYNAMODB_STATE_TABLE_NAME
        self.dynamodb_resource = settings.dynamodb_resource
        self.table = self.dynamodb_resource.Table(self.table_name) if self.dynamodb_resource else None
    
    def get_service_name(self) -> str:
        return "dynamodb"
    
    def check_connection(self) -> ConnectionStatus:
        start_time = time.time()
        
        try:
            if not self.table:
                return ConnectionStatus(
                    service_name=self.get_service_name(),
                    status=ServiceStatus.UNHEALTHY,
                    connected=False,
                    last_check=datetime.now(),
                    error="Table not initialized"
                )
            
            # テーブル状態チェック
            table_status = self.table.table_status
            latency = (time.time() - start_time) * 1000
            
            return ConnectionStatus(
                service_name=self.get_service_name(),
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
                service_name=self.get_service_name(),
                status=ServiceStatus.UNHEALTHY,
                connected=False,
                last_check=datetime.now(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


class MT5ConnectionChecker(IConnectionChecker):
    """MT5接続チェッカー"""
    
    def __init__(self, mt5_connection=None):
        # DIコンテナから注入されるMT5接続インスタンス
        self.mt5_connection = mt5_connection
    
    def get_service_name(self) -> str:
        return "mt5"
    
    def check_connection(self) -> ConnectionStatus:
        start_time = time.time()
        
        try:
            if not self.mt5_connection:
                return ConnectionStatus(
                    service_name=self.get_service_name(),
                    status=ServiceStatus.UNKNOWN,
                    connected=False,
                    last_check=datetime.now(),
                    error="MT5 connection not initialized"
                )
            
            # MT5接続チェック
            is_connected = self.mt5_connection.ensure_connection()
            latency = (time.time() - start_time) * 1000
            
            if is_connected:
                # アカウント情報取得
                account_info = self.mt5_connection.get_account_info()
                
                return ConnectionStatus(
                    service_name=self.get_service_name(),
                    status=ServiceStatus.HEALTHY,
                    connected=True,
                    last_check=datetime.now(),
                    latency_ms=latency,
                    metadata={
                        'balance': account_info.get('balance'),
                        'equity': account_info.get('equity'),
                        'margin_free': account_info.get('margin_free'),
                        'server': account_info.get('server')
                    }
                )
            else:
                return ConnectionStatus(
                    service_name=self.get_service_name(),
                    status=ServiceStatus.UNHEALTHY,
                    connected=False,
                    last_check=datetime.now(),
                    latency_ms=latency,
                    error="MT5 connection failed"
                )
                
        except Exception as e:
            return ConnectionStatus(
                service_name=self.get_service_name(),
                status=ServiceStatus.UNHEALTHY,
                connected=False,
                last_check=datetime.now(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


class RedisConnectionChecker(IConnectionChecker):
    """Redis接続チェッカー（Phase 2用）"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
    
    def get_service_name(self) -> str:
        return "redis"
    
    def check_connection(self) -> ConnectionStatus:
        start_time = time.time()
        
        try:
            if not self.redis_client:
                return ConnectionStatus(
                    service_name=self.get_service_name(),
                    status=ServiceStatus.UNKNOWN,
                    connected=False,
                    last_check=datetime.now(),
                    error="Redis client not initialized"
                )
            
            # Ping実行
            self.redis_client.ping()
            latency = (time.time() - start_time) * 1000
            
            # メモリ情報取得
            info = self.redis_client.info('memory')
            
            return ConnectionStatus(
                service_name=self.get_service_name(),
                status=ServiceStatus.HEALTHY,
                connected=True,
                last_check=datetime.now(),
                latency_ms=latency,
                metadata={
                    'used_memory_mb': info['used_memory'] / (1024 * 1024),
                    'used_memory_peak_mb': info['used_memory_peak'] / (1024 * 1024)
                }
            )
            
        except Exception as e:
            return ConnectionStatus(
                service_name=self.get_service_name(),
                status=ServiceStatus.UNHEALTHY,
                connected=False,
                last_check=datetime.now(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


class SQSConnectionChecker(IConnectionChecker):
    """SQS接続チェッカー"""
    
    def __init__(self):
        self.queue_url = settings.queue_url
        self.sqs_client = settings.sqs_client
    
    def get_service_name(self) -> str:
        return "sqs"
    
    def check_connection(self) -> ConnectionStatus:
        start_time = time.time()
        
        try:
            # キュー属性取得
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )
            latency = (time.time() - start_time) * 1000
            
            attributes = response.get('Attributes', {})
            
            return ConnectionStatus(
                service_name=self.get_service_name(),
                status=ServiceStatus.HEALTHY,
                connected=True,
                last_check=datetime.now(),
                latency_ms=latency,
                metadata={
                    'messages_available': int(attributes.get('ApproximateNumberOfMessages', 0)),
                    'messages_in_flight': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
                }
            )
            
        except Exception as e:
            return ConnectionStatus(
                service_name=self.get_service_name(),
                status=ServiceStatus.UNHEALTHY,
                connected=False,
                last_check=datetime.now(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
```

### 4. Application層: ヘルスチェックユースケース

**ファイル**: `src/application/use_cases/system/health_check.py`

```python
from datetime import datetime
from typing import List, Dict, Optional
import logging

from src.domain.entities.system_status import SystemHealth, ServiceStatus
from src.domain.repositories.kill_switch_repository import IKillSwitchRepository
from src.domain.repositories.connection_checker import IConnectionChecker

logger = logging.getLogger(__name__)

class SystemHealthCheckUseCase:
    """システムヘルスチェックユースケース"""
    
    def __init__(
        self,
        kill_switch_repository: IKillSwitchRepository,
        connection_checkers: List[IConnectionChecker]
    ):
        self.kill_switch_repo = kill_switch_repository
        self.checkers = {
            checker.get_service_name(): checker
            for checker in connection_checkers
        }
    
    def execute(self, services: Optional[List[str]] = None) -> SystemHealth:
        """
        システムヘルスチェック実行
        
        Args:
            services: チェックするサービスのリスト（Noneの場合は全サービス）
        """
        # Kill Switch状態取得
        kill_switch_status = self.kill_switch_repo.get_status_detail()
        
        # 接続状態チェック
        connections = {}
        services_to_check = services or list(self.checkers.keys())
        
        for service_name in services_to_check:
            if service_name in self.checkers:
                try:
                    connections[service_name] = self.checkers[service_name].check_connection()
                except Exception as e:
                    logger.error(f"Health check failed for {service_name}: {e}")
                    # エラー時のフォールバック
                    connections[service_name] = ConnectionStatus(
                        service_name=service_name,
                        status=ServiceStatus.UNKNOWN,
                        connected=False,
                        last_check=datetime.now(),
                        error=str(e)
                    )
        
        # 全体ステータスの判定
        overall_status = self._determine_overall_status(kill_switch_status, connections)
        
        return SystemHealth(
            overall_status=overall_status,
            kill_switch=kill_switch_status,
            connections=connections,
            timestamp=datetime.now()
        )
    
    def _determine_overall_status(
        self,
        kill_switch: Dict,
        connections: Dict
    ) -> ServiceStatus:
        """全体のステータスを判定"""
        
        # Kill Switchが有効なら即UNHEALTHY
        if kill_switch.get('active', False):
            return ServiceStatus.UNHEALTHY
        
        # 必須サービスのチェック
        critical_services = ['dynamodb', 'mt5']
        critical_healthy = all(
            connections.get(service, ConnectionStatus(
                service_name=service,
                status=ServiceStatus.UNKNOWN,
                connected=False,
                last_check=datetime.now()
            )).status == ServiceStatus.HEALTHY
            for service in critical_services
            if service in connections
        )
        
        if not critical_healthy:
            return ServiceStatus.UNHEALTHY
        
        # 任意サービスのチェック
        optional_unhealthy = any(
            conn.status == ServiceStatus.UNHEALTHY
            for name, conn in connections.items()
            if name not in critical_services
        )
        
        if optional_unhealthy:
            return ServiceStatus.DEGRADED
        
        return ServiceStatus.HEALTHY
```

### 5. DIコンテナ拡張

**ファイル**: `src/infrastructure/di/container.py`（拡張）

```python
from typing import List
from infrastructure.monitoring.connection_checkers import (
    DynamoDBConnectionChecker,
    MT5ConnectionChecker,
    RedisConnectionChecker,
    SQSConnectionChecker
)
from application.use_cases.system.health_check import SystemHealthCheckUseCase

class DIContainer:
    """既存実装（省略）"""
    
    def get_connection_checkers(self) -> List[IConnectionChecker]:
        """利用可能な全接続チェッカーを取得"""
        checkers = [
            DynamoDBConnectionChecker(),
            SQSConnectionChecker()
        ]
        
        # MT5が初期化されている場合のみ追加
        try:
            mt5_connection = self.get_mt5_connection()
            checkers.append(MT5ConnectionChecker(mt5_connection))
        except:
            logger.warning("MT5 connection checker not available")
        
        # Redis（Phase 2以降）
        if hasattr(self, '_redis_client') and self._redis_client:
            checkers.append(RedisConnectionChecker(self._redis_client))
        
        return checkers
    
    def get_health_check_use_case(self) -> SystemHealthCheckUseCase:
        """ヘルスチェックユースケースを取得"""
        return SystemHealthCheckUseCase(
            kill_switch_repository=self.get_kill_switch_repository(),
            connection_checkers=self.get_connection_checkers()
        )
```

### 6. Streamlitコントローラー

**ファイル**: `src/presentation/ui/streamlit/controllers/health_controller.py`

```python
import streamlit as st
from typing import Optional, List
from infrastructure.di.container import container

class HealthController:
    """システムヘルスコントローラー"""
    
    def __init__(self):
        self.health_check = container.get_health_check_use_case()
        self.kill_switch_repo = container.get_kill_switch_repository()
    
    @st.cache_data(ttl=30)  # 30秒キャッシュ
    def get_system_health(_self, services: Optional[List[str]] = None):
        """システムヘルス取得"""
        return _self.health_check.execute(services)
    
    def activate_kill_switch(self, reason: str = None) -> bool:
        """Kill Switch有効化"""
        success = self.kill_switch_repo.update_with_reason(
            activate=True,
            reason=reason,
            updated_by="streamlit_user"
        )
        if success:
            st.cache_data.clear()
        return success
    
    def deactivate_kill_switch(self) -> bool:
        """Kill Switch無効化"""
        success = self.kill_switch_repo.update_with_reason(
            activate=False,
            updated_by="streamlit_user"
        )
        if success:
            st.cache_data.clear()
        return success

@st.cache_resource
def get_health_controller() -> HealthController:
    return HealthController()
```

### 7. Streamlit UI表示

**ファイル**: `src/presentation/ui/streamlit/layouts/sidebar.py`（改良版）

```python
import streamlit as st
from datetime import datetime

def render_sidebar(controller, health_status):
    """サイドバーレンダリング"""
    with st.sidebar:
        _render_overall_status(health_status)
        _render_service_connections(health_status.connections)
        _render_kill_switch_controls(controller, health_status.kill_switch)

def _render_overall_status(health_status):
    """全体ステータス表示"""
    st.markdown("#### 📡 システムステータス")
    
    status_icons = {
        'healthy': ('✅', 'success'),
        'degraded': ('⚠️', 'warning'),
        'unhealthy': ('❌', 'error'),
        'unknown': ('❓', 'info')
    }
    
    icon, status_type = status_icons.get(
        health_status.overall_status.value,
        ('❓', 'info')
    )
    
    if health_status.kill_switch['active']:
        st.error("🚨 **KILL SWITCH ACTIVE**")
    elif health_status.overall_status.value == 'healthy':
        st.success(f"{icon} システム正常稼働中")
    elif health_status.overall_status.value == 'degraded':
        st.warning(f"{icon} 一部サービス異常")
    else:
        st.error(f"{icon} システム異常")
    
    # 取引可否
    if health_status.is_tradeable:
        st.success("💹 取引可能")
    else:
        st.error("🚫 取引不可")

def _render_service_connections(connections):
    """各サービス接続状態"""
    st.markdown("#### 🔌 サービス接続")
    
    # サービスの表示順序と表示名
    service_display = {
        'dynamodb': 'DynamoDB',
        'mt5': 'MT5',
        'sqs': 'SQS',
        'redis': 'Redis',
        's3': 'S3'
    }
    
    for service_key, display_name in service_display.items():
        if service_key in connections:
            conn = connections[service_key]
            
            # 接続状態アイコン
            if conn.connected:
                icon = "🟢"
            else:
                icon = "🔴"
            
            # 基本情報
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{icon} {display_name}")
            with col2:
                if conn.latency_ms:
                    st.text(f"{conn.latency_ms:.0f}ms")
            
            # メタデータ表示（サービス別）
            if conn.metadata:
                if service_key == 'mt5' and conn.connected:
                    st.caption(f"Balance: ${conn.metadata.get('balance', 0):,.2f}")
                elif service_key == 'sqs' and conn.connected:
                    msgs = conn.metadata.get('messages_available', 0)
                    st.caption(f"Messages: {msgs}")
                elif service_key == 'redis' and conn.connected:
                    mem = conn.metadata.get('used_memory_mb', 0)
                    st.caption(f"Memory: {mem:.1f}MB")
            
            # エラー表示
            if conn.error:
                st.caption(f"⚠️ {conn.error[:50]}...")
    
    # リフレッシュボタン
    if st.button("🔄 更新", key="refresh_health"):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"最終確認: {datetime.now().strftime('%H:%M:%S')}")
```

---

## 📊 利点

### 1. 拡張性
- 新しいサービスは`IConnectionChecker`を実装するだけ
- DIコンテナの`get_connection_checkers()`に追加
- UI側の変更は最小限

### 2. 統一性
- すべてのサービスが同じインターフェース
- 共通の状態モデル（`ConnectionStatus`）
- 一貫したエラーハンドリング

### 3. 柔軟性
- 部分的なヘルスチェック可能
- サービスごとのメタデータ対応
- Critical/Optionalサービスの区別

### 4. パフォーマンス
- キャッシュによる負荷軽減
- 並列チェック可能（将来）
- 必要なサービスのみチェック

---

## 🚀 新サービス追加例

```python
# 新しいサービスチェッカーを追加
class YFinanceConnectionChecker(IConnectionChecker):
    def get_service_name(self) -> str:
        return "yfinance"
    
    def check_connection(self) -> ConnectionStatus:
        # yfinance APIチェック実装
        pass

# DIコンテナに追加（1行）
checkers.append(YFinanceConnectionChecker())

# UI側は自動的に表示される
```
