# 📋 AXIA Week 3 実装計画書

**作成日**: 2025年10月18日  
**実装期間**: 2025年10月19日（土）〜 10月21日（月）  
**目標**: 注文機能完全実装 + リアルタイムデータ対応

---

## 🎯 Week 3の目標

```
優先度★★★（必須）:
1. ✅ 注文機能の完全実装
   - SQS order_publisher実装
   - Streamlit → SQS → order_manager → MT5の完全連携
   - 注文結果のリアルタイム表示

2. ✅ リアルタイムデータ対応
   - OhlcvDataProvider統合
   - Redis鮮度メタデータ機能
   - データ鮮度の可視化
   - 手動更新機能（🔄最新ボタン）

3. ✅ Windows EC2デプロイ
   - タスクスケジューラ設定
   - 4プロセス自動起動
   - 統合動作確認
```

---

## 📅 3日間スケジュール

### **Day 1（土）: 注文機能実装（8時間）**

```
午前（4時間）: SQS注文送信
  ├─ order_publisher.py実装（2時間）
  ├─ DIコンテナ更新（30分）
  └─ ローカルテスト（1.5時間）

午後（4時間）: Streamlit注文UI
  ├─ trading_page.py更新（3時間）
  │  ├─ 注文パネル拡張
  │  ├─ BUY/SELLボタン実装
  │  └─ SQS送信処理
  └─ ローカル統合テスト（1時間）
```

### **Day 2（日）: リアルタイムデータ対応（8時間）**

```
午前（4時間）: Redis鮮度メタデータ
  ├─ RedisOhlcvDataRepository拡張（2時間）
  │  ├─ save_ohlcv（メタデータ付き）
  │  └─ load_ohlcv_with_metadata
  └─ OhlcvDataProvider鮮度チェック（2時間）
     ├─ _get_max_age実装
     └─ 鮮度判定ロジック

午後（4時間）: Streamlit UI更新
  ├─ chart_data_source.py統合（2時間）
  │  ├─ OhlcvDataProvider利用
  │  └─ force_refresh実装
  └─ trading_page.py UI拡張（2時間）
     ├─ データ鮮度表示
     ├─ 🔄最新ボタン
     └─ データソース情報表示
```

### **Day 3（月）: EC2デプロイ + 動作確認（8時間）**

```
午前（4時間）: Windows EC2構築
  ├─ RDP接続・環境確認（30分）
  ├─ Git Pull + 依存関係更新（1時間）
  ├─ タスクスケジューラ設定（2時間）
  └─ サービス起動確認（30分）

午後（4時間）: 統合テスト
  ├─ チャート表示テスト（1時間）
  ├─ 注文機能テスト（2時間）
  │  ├─ BUY注文 → SQS → MT5
  │  ├─ SELL注文 → SQS → MT5
  │  └─ Kill Switch動作確認
  └─ 最終確認 + ドキュメント（1時間）
```

---

## 🔧 Day 1: 注文機能実装

### 1-1. SQS order_publisher実装（2時間）

**ファイル**: `src/infrastructure/gateways/messaging/sqs/order_publisher.py`

```python
# src/infrastructure/gateways/messaging/sqs/order_publisher.py

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SQSOrderPublisher:
    """SQS注文送信クラス"""
    
    def __init__(self, queue_url: str, sqs_client):
        """
        初期化
        
        Args:
            queue_url: SQSキューURL
            sqs_client: boto3 SQSクライアント
        """
        self.queue_url = queue_url
        self.sqs_client = sqs_client
        logger.info(f"SQSOrderPublisher initialized: {queue_url}")
    
    def send_order(self, order_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        注文メッセージをSQSに送信
        
        Args:
            order_data: {
                'symbol': str,           # 通貨ペア
                'order_action': str,     # 'BUY' or 'SELL'
                'order_type': str,       # 'MARKET' or 'LIMIT'
                'lot_size': float,       # ロット数
                'tp_price': float,       # 利確価格
                'sl_price': float,       # 損切価格
                'comment': str           # コメント
            }
        
        Returns:
            tuple: (成功フラグ, メッセージID or エラーメッセージ)
        """
        try:
            # バリデーション
            if not self._validate_order_data(order_data):
                return False, "Invalid order data"
            
            # JSON化
            message_body = json.dumps(order_data)
            
            # SQS送信
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            
            message_id = response.get('MessageId')
            
            logger.info(
                f"Order sent successfully: "
                f"MessageId={message_id}, "
                f"{order_data['symbol']} {order_data['order_action']} "
                f"{order_data['lot_size']} lot"
            )
            
            return True, message_id
            
        except Exception as e:
            error_msg = f"Failed to send order: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _validate_order_data(self, order_data: Dict[str, Any]) -> bool:
        """注文データのバリデーション"""
        required_fields = [
            'symbol', 'order_action', 'order_type',
            'lot_size', 'tp_price', 'sl_price'
        ]
        
        for field in required_fields:
            if field not in order_data:
                logger.error(f"Missing required field: {field}")
                return False
        
        # order_actionチェック
        if order_data['order_action'] not in ['BUY', 'SELL']:
            logger.error(f"Invalid order_action: {order_data['order_action']}")
            return False
        
        # lot_sizeチェック
        if order_data['lot_size'] <= 0:
            logger.error(f"Invalid lot_size: {order_data['lot_size']}")
            return False
        
        return True
```

---

### 1-2. DIコンテナ更新（30分）

**ファイル**: `src/infrastructure/di/container.py`

```python
# src/infrastructure/di/container.py（追加部分）

from src.infrastructure.gateways.messaging.sqs.order_publisher import SQSOrderPublisher

class DIContainer:
    def __init__(self):
        # 既存の初期化...
        self._sqs_order_publisher = None
    
    def get_sqs_order_publisher(self) -> SQSOrderPublisher:
        """SQS注文送信クラスを取得"""
        if not self._sqs_order_publisher:
            self._sqs_order_publisher = SQSOrderPublisher(
                queue_url=self.settings.queue_url,
                sqs_client=self.settings.sqs_client
            )
        return self._sqs_order_publisher
```

---

### 1-3. trading_page.py更新（3時間）

**ファイル**: `src/presentation/ui/streamlit/pages/trading_page.py`

```python
# src/presentation/ui/streamlit/pages/trading_page.py

import streamlit as st
from components.trading_charts.price_chart import PriceChartComponent
from components.trading_charts.chart_data_source import get_chart_data_source
from src.infrastructure.di.container import DIContainer

container = DIContainer()

def render_trading_page():
    """チャートページのレンダリング"""
    
    # データソース取得
    data_source = get_chart_data_source()
    
    # 注文パブリッシャー取得
    order_publisher = container.get_sqs_order_publisher()
    
    # チャート設定
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        chart_symbol = st.selectbox(
            "通貨ペア",
            ["USDJPY", "EURJPY", "GBPJPY", "EURUSD", "GBPUSD"],
            key="chart_symbol"
        )
    
    with col2:
        chart_timeframe = st.selectbox(
            "時間足",
            ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            index=4,  # H1
            key="chart_timeframe"
        )
    
    with col3:
        days = st.number_input("日数", 1, 90, 30, key="chart_days")
    
    with col4:
        if st.button("🔄 リロード", key="refresh_chart"):
            st.rerun()
    
    # 注文パネル
    _render_order_panel(chart_symbol, order_publisher)
    
    # チャート表示
    _render_chart(chart_symbol, chart_timeframe)


def _render_order_panel(chart_symbol: str, order_publisher):
    """注文パネルのレンダリング（完全実装版）"""
    with st.expander("📃 注文パネル", expanded=True):
        # 注文設定行
        order_cols = st.columns([1, 1, 1, 1, 1])
        
        with order_cols[0]:
            lot_size = st.number_input(
                "ロット",
                min_value=0.01,
                max_value=10.0,
                value=0.10,
                step=0.01,
                format="%.2f",
                key="order_lot"
            )
        
        with order_cols[1]:
            tp_pips = st.number_input(
                "TP (pips)",
                min_value=0,
                max_value=500,
                value=50,
                step=5,
                key="order_tp"
            )
        
        with order_cols[2]:
            sl_pips = st.number_input(
                "SL (pips)",
                min_value=0,
                max_value=500,
                value=25,
                step=5,
                key="order_sl"
            )
        
        with order_cols[3]:
            # リスク計算
            risk = lot_size * sl_pips * 100
            profit = lot_size * tp_pips * 100
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small>リスク: ¥{risk:,.0f}<br>
            利益: ¥{profit:,.0f}</small>
            </div>
            """, unsafe_allow_html=True)
        
        with order_cols[4]:
            # R/R比表示
            rr = tp_pips / sl_pips if sl_pips > 0 else 0
            color = "green" if rr >= 2 else "orange" if rr >= 1 else "red"
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
            <small>R/R比<br>
            <span style='color: {color}; font-size: 18px; font-weight: bold;'>
            {rr:.2f}
            </span></small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # BUY/SELLボタン
        buy_col, sell_col = st.columns(2)
        
        with buy_col:
            if st.button(
                f"🔼 BUY {chart_symbol}",
                key="execute_buy",
                type="primary",
                use_container_width=True
            ):
                _execute_order(
                    chart_symbol, "BUY", lot_size,
                    tp_pips, sl_pips, order_publisher
                )
        
        with sell_col:
            if st.button(
                f"🔽 SELL {chart_symbol}",
                key="execute_sell",
                type="secondary",
                use_container_width=True
            ):
                _execute_order(
                    chart_symbol, "SELL", lot_size,
                    tp_pips, sl_pips, order_publisher
                )


def _execute_order(
    symbol: str,
    action: str,
    lot_size: float,
    tp_pips: int,
    sl_pips: int,
    order_publisher
):
    """
    注文実行（SQS送信）
    
    処理フロー:
    1. 現在価格取得（ダミー実装）
    2. TP/SL価格計算
    3. 注文データ作成
    4. SQS送信
    5. 結果表示
    """
    try:
        # TODO: OhlcvDataProviderから現在価格取得
        # 現状はダミー価格
        current_price = 150.0  # USDJPY想定
        
        # TP/SL価格計算
        pip_value = 0.01  # USDJPYの場合（他通貨ペアは要調整）
        
        if action == "BUY":
            tp_price = current_price + (tp_pips * pip_value)
            sl_price = current_price - (sl_pips * pip_value)
        else:  # SELL
            tp_price = current_price - (tp_pips * pip_value)
            sl_price = current_price + (sl_pips * pip_value)
        
        # 注文データ作成
        order_data = {
            'symbol': symbol,
            'order_action': action,
            'order_type': 'MARKET',
            'lot_size': lot_size,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'comment': 'Streamlit_Manual_Order'
        }
        
        # SQS送信
        with st.spinner('注文送信中...'):
            success, message = order_publisher.send_order(order_data)
        
        if success:
            st.success(f"""
            ✅ {action}注文を送信しました
            
            **注文内容**:
            - 通貨ペア: {symbol}
            - ロット: {lot_size}
            - TP: {tp_price:.3f} ({tp_pips} pips)
            - SL: {sl_price:.3f} ({sl_pips} pips)
            - R/R比: {tp_pips/sl_pips:.2f}
            
            **処理状況**:
            - MessageID: `{message[:20]}...`
            - order_managerで処理中...
            
            💡 ポジションページで実行結果を確認できます
            """)
        else:
            st.error(f"""
            ❌ 注文送信に失敗しました
            
            **エラー**: {message}
            """)
            
    except Exception as e:
        st.error(f"❌ 注文処理エラー: {e}")
        logger.error(f"Order execution error: {e}", exc_info=True)


def _render_chart(symbol: str, timeframe: str):
    """チャートのレンダリング（既存）"""
    try:
        fig = PriceChartComponent.render_chart(
            symbol=symbol,
            timeframe=timeframe,
            days=30
        )
        st.plotly_chart(
            fig,
            config={'displayModeBar': False},
            use_container_width=True
        )
    except Exception as e:
        st.error(f"チャート表示エラー: {e}")
```

---

## 🔧 Day 2: リアルタイムデータ対応

### 2-1. Redis鮮度メタデータ機能（2時間）

**ファイル**: `src/infrastructure/persistence/redis/redis_ohlcv_data_repository.py`

```python
# src/infrastructure/persistence/redis/redis_ohlcv_data_repository.py（追加部分）

import json
from datetime import datetime
import pytz

class RedisOhlcvDataRepository:
    # 既存コード...
    
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> bool:
        """
        OHLCVデータをRedisに保存（メタデータ付き）
        
        保存内容:
        - {key}:data - シリアライズされたDataFrame
        - {key}:meta - メタデータ（更新時刻、行数）
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            
            # データシリアライズ
            data = self._serialize_dataframe(df)
            
            # メタデータ作成
            metadata = {
                'updated_at': datetime.now(pytz.UTC).isoformat(),
                'row_count': len(df),
                'symbol': symbol,
                'timeframe': timeframe
            }
            
            # パイプラインで一括保存
            pipeline = self.redis_client.pipeline()
            pipeline.set(f"{key}:data", data)
            pipeline.set(f"{key}:meta", json.dumps(metadata))
            pipeline.expire(f"{key}:data", self.ttl)
            pipeline.expire(f"{key}:meta", self.ttl)
            results = pipeline.execute()
            
            if all(results):
                logger.info(
                    f"Saved to Redis: {symbol} {timeframe} "
                    f"({len(df)} rows, TTL={self.ttl}s)"
                )
                return True
            else:
                logger.error(f"Failed to save to Redis: {symbol} {timeframe}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving to Redis: {e}", exc_info=True)
            return False
    
    def load_ohlcv_with_metadata(
        self,
        symbol: str,
        timeframe: str,
        days: int = 1
    ) -> tuple[pd.DataFrame | None, dict | None]:
        """
        OHLCVデータとメタデータを取得
        
        Returns:
            (DataFrame, metadata): データとメタデータのタプル
            (None, None): データが存在しない場合
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            
            # データとメタデータを取得
            data = self.redis_client.get(f"{key}:data")
            meta_json = self.redis_client.get(f"{key}:meta")
            
            if not data or not meta_json:
                logger.debug(f"Cache miss: {symbol} {timeframe}")
                return None, None
            
            # デシリアライズ
            df = self._deserialize_dataframe(data)
            metadata = json.loads(meta_json)
            
            # 更新時刻をdatetimeに変換
            metadata['updated_at'] = datetime.fromisoformat(
                metadata['updated_at']
            )
            
            # 期間フィルタリング
            if days and days > 0:
                from datetime import timedelta
                cutoff = datetime.now(pytz.UTC) - timedelta(days=days)
                df = df[df.index >= cutoff]
            
            age = datetime.now(pytz.UTC) - metadata['updated_at']
            
            logger.info(
                f"Cache hit: {symbol} {timeframe} "
                f"({len(df)} rows, age={age.total_seconds():.0f}s)"
            )
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"Error loading from Redis: {e}", exc_info=True)
            return None, None
```

---

### 2-2. OhlcvDataProvider鮮度チェック（2時間）

**ファイル**: `src/infrastructure/gateways/market_data/ohlcv_data_provider.py`

```python
# src/infrastructure/gateways/market_data/ohlcv_data_provider.py（追加部分）

from datetime import datetime, timedelta
import pytz

class OhlcvDataProvider:
    # 既存コード...
    
    def get_data(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 1,
        use_case: str = 'trading'
    ) -> tuple[pd.DataFrame | None, dict]:
        """
        統合データ取得（鮮度チェック付き）
        """
        metadata = {
            'requested_at': datetime.now(pytz.UTC),
            'symbol': symbol,
            'timeframe': timeframe,
            'use_case': use_case
        }
        
        # 1. Redisキャッシュチェック（メタデータ付き）
        if self.ohlcv_cache:
            df, cache_meta = self.ohlcv_cache.load_ohlcv_with_metadata(
                symbol, timeframe, days=period_days
            )
            
            if df is not None and cache_meta:
                # 鮮度チェック
                age = datetime.now(pytz.UTC) - cache_meta['updated_at']
                max_age = self._get_max_age(timeframe)
                
                if age < max_age:
                    # 新鮮なデータ
                    metadata.update({
                        'source': 'redis',
                        'cache_hit': True,
                        'data_age': age.total_seconds(),
                        'fresh': True
                    })
                    logger.info(
                        f"Fresh cache hit: {symbol} {timeframe} "
                        f"(age: {age.total_seconds():.0f}s)"
                    )
                    return df, metadata
                else:
                    # 古いデータ
                    logger.info(
                        f"Stale cache: {symbol} {timeframe} "
                        f"(age: {age.total_seconds():.0f}s > "
                        f"max: {max_age.total_seconds():.0f}s)"
                    )
                    metadata['stale_cache_age'] = age.total_seconds()
        
        # 2. データソースから取得
        sources = self._get_source_priority(use_case, period_days)
        
        for source_name in sources:
            df = self._fetch_from_source(
                source_name, symbol, timeframe, period_days
            )
            
            if df is not None:
                # 取得成功 → Redisに自動保存
                self._cache_result(df, symbol, timeframe)
                
                metadata.update({
                    'source': source_name,
                    'cache_hit': False,
                    'rows': len(df),
                    'fresh': True
                })
                
                return df, metadata
        
        # 3. 全ソース失敗
        metadata['error'] = 'All sources failed'
        return None, metadata
    
    def _get_max_age(self, timeframe: str) -> timedelta:
        """
        許容される最大データ年齢
        
        時間足に応じて動的に設定:
        - 短い時間足: より頻繁な更新が必要
        - 長い時間足: 古いデータでも許容
        """
        age_map = {
            'M1': timedelta(minutes=5),   # 5分以内
            'M5': timedelta(minutes=15),  # 15分以内
            'M15': timedelta(minutes=30), # 30分以内
            'M30': timedelta(hours=1),    # 1時間以内
            'H1': timedelta(hours=2),     # 2時間以内
            'H4': timedelta(hours=6),     # 6時間以内
            'D1': timedelta(days=1),      # 1日以内
            'W1': timedelta(days=7),      # 1週間以内
            'MN1': timedelta(days=30),    # 1ヶ月以内
        }
        return age_map.get(timeframe, timedelta(hours=1))
```

---

### 2-3. chart_data_source.py統合（2時間）

**ファイル**: `src/presentation/ui/streamlit/components/trading_charts/chart_data_source.py`

```python
# src/presentation/ui/streamlit/components/trading_charts/chart_data_source.py

import streamlit as st
import logging
from src.infrastructure.di.container import DIContainer

logger = logging.getLogger(__name__)
container = DIContainer()

class ChartDataSource:
    """チャートデータ取得クラス（OhlcvDataProvider統合版）"""
    
    def __init__(self):
        try:
            self.data_provider = container.get_ohlcv_data_provider()
            logger.info("ChartDataSource initialized with OhlcvDataProvider")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            self.data_provider = None
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_ohlcv_data(
        _self,
        symbol: str,
        timeframe: str,
        period_days: int = 30
    ) -> tuple[pd.DataFrame | None, dict]:
        """
        OHLCVデータを取得（メタデータ付き）
        
        Returns:
            (DataFrame, metadata): データとメタデータのタプル
        """
        if _self.data_provider is None:
            return None, {'error': 'Data provider not available'}
        
        try:
            df, metadata = _self.data_provider.get_data(
                symbol=symbol,
                timeframe=timeframe,
                period_days=period_days,
                use_case='chart'
            )
            
            if df is None or df.empty:
                return None, metadata
            
            logger.info(
                f"Data loaded: {symbol} {timeframe}, "
                f"source={metadata.get('source')}, rows={len(df)}"
            )
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return None, {'error': str(e)}
    
    def force_refresh(
        self,
        symbol: str,
        timeframe: str,
        period_days: int = 30
    ) -> tuple[pd.DataFrame | None, dict]:
        """
        キャッシュをクリアして強制的に最新データを取得
        """
        # Streamlitキャッシュをクリア
        st.cache_data.clear()
        
        # 再取得（force_source='mt5'を指定して最新データを取得）
        if self.data_provider:
            return self.data_provider.get_data(
                symbol=symbol,
                timeframe=timeframe,
                period_days=period_days,
                use_case='chart',
                force_source='mt5'  # MT5から強制取得
            )
        return None, {'error': 'Data provider not available'}


@st.cache_resource
def get_chart_data_source() -> ChartDataSource:
    """シングルトンとしてChartDataSourceを取得"""
    return ChartDataSource()
```

---

### 2-4. trading_page.py UI拡張（2時間）

**ファイル**: `src/presentation/ui/streamlit/pages/trading_page.py`（Day 1の続き）

```python
# trading_page.pyに追加

def render_trading_page():
    """チャートページ（リアルタイム対応版）"""
    
    # ... 既存のコード（Day 1実装分）...
    
    # 🔄最新ボタン追加（col4の部分を更新）
    with col4:
        if st.button("🔄 最新", help="MT5から最新データを取得"):
            with st.spinner("最新データ取得中..."):
                df, metadata = data_source.force_refresh(
                    chart_symbol, chart_timeframe, days
                )
            if df is not None:
                st.success("✅ 最新データを取得しました")
                st.rerun()
            else:
                st.error("❌ データ取得に失敗しました")
    
    # 注文パネル（既存）
    _render_order_panel(chart_symbol, order_publisher)
    
    # データ取得
    with st.spinner('Loading chart...'):
        df, metadata = data_source.get_ohlcv_data(
            chart_symbol, chart_timeframe, days
        )
    
    if df is not None:
        # データ鮮度情報表示 ★追加★
        _render_data_freshness(metadata)
        
        # データソース情報（サイドバー）★追加★
        _render_data_info_sidebar(chart_symbol, chart_timeframe, metadata)
        
        # チャート描画
        _render_chart_display(df, chart_symbol, chart_timeframe)
    else:
        st.error("データ取得に失敗しました")
        if 'error' in metadata:
            with st.expander("エラー詳細"):
                st.code(metadata['error'])


def _render_data_freshness(metadata: dict):
    """データ鮮度情報の表示"""
    if 'data_age' in metadata:
        age_seconds = metadata['data_age']
        
        if age_seconds < 300:  # 5分以内
            st.success(f"✅ 最新データ（{int(age_seconds)}秒前）")
        elif age_seconds < 3600:  # 1時間以内
            minutes = int(age_seconds / 60)
            st.info(f"ℹ️ {minutes}分前のデータ")
        else:  # 1時間以上
            hours = int(age_seconds / 3600)
            st.warning(
                f"⚠️ {hours}時間前のデータ "
                f"（🔄ボタンで更新推奨）"
            )
    elif metadata.get('fresh'):
        st.success("✅ 最新データ")


def _render_data_info_sidebar(symbol: str, timeframe: str, metadata: dict):
    """データソース情報をサイドバーに表示"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📡 Data Info")
        
        source = metadata.get('source', 'unknown')
        emoji_map = {
            'redis': '⚡',
            's3': '📦',
            'mt5': '🔌',
            'yfinance': '🌐'
        }
        emoji = emoji_map.get(source, '❓')
        
        st.info(f"{emoji} **{source.upper()}**")
        
        if 'rows' in metadata:
            st.metric("Rows", f"{metadata['rows']:,}")
        
        if 'data_age' in metadata:
            age = int(metadata['data_age'])
            if age < 60:
                st.caption(f"Age: {age}秒前")
            elif age < 3600:
                st.caption(f"Age: {age//60}分前")
            else:
                st.caption(f"Age: {age//3600}時間前")
        
        if metadata.get('cache_hit'):
            st.caption("✅ Cache Hit")
        else:
            st.caption("🔄 Fresh Fetch")


def _render_chart_display(df, symbol, timeframe):
    """チャート描画"""
    try:
        fig = PriceChartComponent.render_chart(
            symbol=symbol,
            timeframe=timeframe,
            days=30
        )
        st.plotly_chart(
            fig,
            config={'displayModeBar': False},
            use_container_width=True
        )
    except Exception as e:
        st.error(f"チャート表示エラー: {e}")
```

---

## 🔧 Day 3: Windows EC2デプロイ

### 3-1. タスクスケジューラ設定（2時間）

**Windows タスクスケジューラ設定手順**

#### 1. order_managerサービス

```xml
名前: AXIA_Order_Manager
トリガー: システム起動時
アクション:
  プログラム: C:\AXIA\.venv\Scripts\python.exe
  引数: C:\AXIA\src\presentation\cli\run_order_processor.py
  開始: C:\AXIA
設定:
  - 最高の特権で実行
  - タスクの実行時間制限: 無効
  - タスク失敗時: 10分後に再起動（最大3回）
```

#### 2. data_collectorサービス

```xml
名前: AXIA_Data_Collector
トリガー: 毎日 深夜2時
アクション:
  プログラム: C:\AXIA\.venv\Scripts\python.exe
  引数: C:\AXIA\src\presentation\cli\run_data_collector.py
  開始: C:\AXIA
設定:
  - 最高の特権で実行
  - タスク失敗時: 5分後に再起動（最大2回）
```

#### 3. Streamlitサービス

```xml
名前: AXIA_Streamlit
トリガー: システム起動時
アクション:
  プログラム: C:\AXIA\.venv\Scripts\streamlit.exe
  引数: run C:\AXIA\src\presentation\ui\streamlit\app.py --server.port=8501 --server.address=0.0.0.0
  開始: C:\AXIA
設定:
  - 最高の特権で実行
  - タスクの実行時間制限: 無効
```

#### 4. MT5起動

```xml
名前: AXIA_MT5
トリガー: システム起動時
アクション:
  プログラム: C:\Program Files\MetaTrader 5\terminal64.exe
  引数: /config:C:\AXIA\config\mt5_config.ini
設定:
  - 最高の特権で実行
```

---

### 3-2. 統合テストチェックリスト

#### チャート表示テスト

```
✓ USDJPY H1 30日分表示
✓ データソース表示（Redis/S3/MT5）
✓ データ鮮度表示（✅/ℹ️/⚠️）
✓ 🔄最新ボタン動作
✓ チャート表示速度（目標: 1秒以内）
```

#### 注文機能テスト

```
✓ BUY注文送信
  - Streamlit UI入力
  - SQS送信成功
  - order_manager受信
  - MT5注文実行
  - DynamoDB保存

✓ SELL注文送信
  - 同様の流れ

✓ バリデーション
  - 不正なロット数
  - 不正なTP/SL
  - Kill Switch有効時

✓ エラーハンドリング
  - MT5接続エラー
  - SQS送信エラー
```

#### Kill Switch動作確認

```
✓ DynamoDBで有効化
✓ 注文送信ブロック
✓ order_manager停止
✓ UI警告表示
```

---

## ✅ Week 3完了条件

### 必須機能

```
✅ 注文機能完全実装
  - SQS order_publisher動作
  - Streamlit → SQS → order_manager → MT5連携
  - 注文結果表示

✅ リアルタイムデータ対応
  - OhlcvDataProvider統合
  - Redis鮮度メタデータ
  - データ鮮度可視化（✅/ℹ️/⚠️）
  - 🔄最新ボタン動作

✅ Windows EC2デプロイ
  - タスクスケジューラ4プロセス
  - 自動起動確認
  - 統合テスト完了
```

### パフォーマンス指標

| 項目 | 目標 | 判定基準 |
|------|------|---------|
| **注文送信** | 1秒以内 | SQS送信完了まで |
| **チャート表示** | 1秒以内 | 初回表示 |
| **データ鮮度判定** | 即座（5ms） | メタデータ確認 |
| **🔄最新更新** | 2秒以内 | MT5から取得 |

---

## 📊 実装統計

### 新規・更新ファイル

| ファイル | 状態 | 行数 |
|---------|------|------|
| `order_publisher.py` | 🆕新規 | ~120行 |
| `container.py` | 🔄更新 | +15行 |
| `redis_ohlcv_data_repository.py` | 🔄更新 | +80行 |
| `ohlcv_data_provider.py` | 🔄更新 | +60行 |
| `chart_data_source.py` | 🔄更新 | +50行 |
| `trading_page.py` | 🔄更新 | +200行 |

**合計**: 約525行

---

## 🚀 実装開始コマンド

```bash
# === Day 1: ローカル開発（注文機能） ===

# 1. ブランチ作成
git checkout -b feature/week3-order-realtime

# 2. 注文機能実装
mkdir -p src/infrastructure/gateways/messaging/sqs
touch src/infrastructure/gateways/messaging/sqs/order_publisher.py
# → 上記コードを実装

# 3. Streamlit更新
nano src/presentation/ui/streamlit/pages/trading_page.py

# 4. ローカルテスト
streamlit run src/presentation/ui/streamlit/app.py

# === Day 2: リアルタイムデータ対応 ===

# 5. Redis鮮度機能
nano src/infrastructure/persistence/redis/redis_ohlcv_data_repository.py

# 6. OhlcvDataProvider更新
nano src/infrastructure/gateways/market_data/ohlcv_data_provider.py

# 7. chart_data_source統合
nano src/presentation/ui/streamlit/components/trading_charts/chart_data_source.py

# 8. コミット
git add .
git commit -m "feat: Week 3 - Order + Real-time data complete"
git push origin feature/week3-order-realtime

# === Day 3: Windows EC2デプロイ ===

# 9. RDP接続
mstsc /v:<EC2-PUBLIC-IP>

# 10. EC2でPull
cd C:\AXIA
git pull origin feature/week3-order-realtime

# 11. タスクスケジューラ設定
# → GUI操作

# 12. 統合テスト実施
# → ブラウザで確認: http://<EC2-IP>:8501

完了！
```

---

## 💡 次のステップ（Week 4以降）

### Week 4: ポートフォリオ準備

```
1. README.md充実
2. スクリーンショット作成
3. デモ動画録画
4. GitHub Public化
5. セキュリティ最終チェック
```

### Phase 3: 高度化

```
1. S3並列読み込み
2. バックテスト機能
3. パフォーマンス分析
4. MLモデル統合
```

---
