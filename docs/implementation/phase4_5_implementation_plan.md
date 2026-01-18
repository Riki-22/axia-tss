# Phase 4, 5 詳細実装計画書

**作成日**: 2026-01-13  
**目的**: バックテストコード分析と既存資料に基づく Phase 4（シグナル生成）、Phase 5（バックテスト）の実装計画策定

---

## 目次

- [1. バックテストコード分析](#1-バックテストコード分析)
- [2. Phase 4: シグナル生成機能 詳細計画](#2-phase-4-シグナル生成機能-詳細計画)
- [3. Phase 5: バックテスト機能 詳細計画](#3-phase-5-バックテスト機能-詳細計画)
- [4. Phase 3.5との統合戦略](#4-phase-35との統合戦略)
- [5. 実装スケジュール](#5-実装スケジュール)

---

## 1. バックテストコード分析

### 1.1 既存実装の概要

添付されたバックテストコードは、**SageMaker Jupyter環境で動作する完成度の高いバックテストシステム**です。

#### 実装済み機能

| カテゴリ | 機能 | 実装状況 | コード行数 |
|---------|------|---------|-----------|
| **データ取得** | S3からParquet読み込み | ✅ 完成 | ~30行 |
| **テクニカル分析** | | | |
| - ダウ理論 | トレンド判定 | ✅ 完成 | ~40行 |
| - S/Rゾーン | DBSCAN + find_peaks | ✅ 完成 | ~80行 |
| - ピボットポイント | 日足からP/S1/R1/S2/R2 | ✅ 完成 | ~30行 |
| **シグナル生成** | | | |
| - S/Rタッチ | サポレジ接触検出 | ✅ 完成 | ~20行 |
| - RSI | 30/70クロス | ✅ 完成 | ~15行 |
| - MACD | ゴールデン/デッドクロス | ✅ 完成 | ~15行 |
| - ボリンジャーバンド | ブレイクアウト | ✅ 完成 | ~15行 |
| **シグナル統合** | 投票システム（2票以上） | ✅ 完成 | ~40行 |
| **リスク管理** | | | |
| - RR比チェック | 1.5倍以上 | ✅ 完成 | ~10行 |
| - 固定SL/TP | サポレジベース | ✅ 完成 | ~20行 |
| - トレーリングストップ | RR1.5倍で発動 | ✅ 完成 | ~30行 |
| **バックテストエンジン** | vectorbt統合 | ✅ 完成 | ~30行 |
| **可視化** | Plotlyグラフ | ✅ 完成 | ~80行 |

**合計**: 約455行（高度に最適化されたコード）

#### 技術スタック

```python
# 主要ライブラリ
import vectorbt as vbt      # バックテストフレームワーク
import talib                # テクニカル指標計算
from scipy.signal import find_peaks  # ピーク検出
from sklearn.cluster import DBSCAN   # AIクラスタリング
import plotly.graph_objects as go    # 可視化
```

### 1.2 アーキテクチャ分析

#### 現在の実装（Jupyter Notebook）

```
┌─────────────────────────────────────────┐
│  Jupyter Notebook（モノリシック）         │
│                                         │
│  1. データ取得（S3）                      │
│  2. テクニカル分析                        │
│  3. シグナル生成                          │
│  4. バックテスト実行                      │
│  5. パフォーマンス評価                     │
│  6. 可視化                               │
│                                         │
│  全てが1つのノートブックに統合            │
└─────────────────────────────────────────┘
```

**特徴**:
- ✅ 全機能が動作確認済み
- ✅ 実践的なパラメータチューニング済み
- ❌ 本番システムと分離
- ❌ リアルタイム実行不可
- ❌ API化されていない

#### 目標アーキテクチャ（Phase 4, 5完了後）

```
┌─────────────────────────────────────────────────────┐
│              Streamlit UI                            │
│  - リアルタイムシグナル表示                           │
│  - バックテスト実行                                   │
│  - パフォーマンス比較                                 │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│            Application Layer                         │
│  GenerateSignalsUseCase                             │
│  RunBacktestUseCase                                 │
│  CompareBacktestVsRealUseCase  ← Phase 3.5必須      │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│               Domain Layer                           │
│  Signal Entity                                       │
│  SignalIntegrationService ← Jupyter移植              │
│  BacktestEngine ← Jupyter移植                       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│          Infrastructure Layer                        │
│  TechnicalAnalysisProvider ← Jupyter移植            │
│  - ダウ理論                                          │
│  - S/Rゾーン（DBSCAN）                               │
│  - ピボット                                          │
│  SignalRepository (DynamoDB)                         │
│  PositionRepository (DynamoDB) ← Phase 3.5必須       │
└─────────────────────────────────────────────────────┘
```

### 1.3 コード移植の難易度分析

#### 移植が容易な部分 ✅

| 機能 | 理由 | 移植工数 |
|------|------|---------|
| **テクニカル分析** | 純粋な計算ロジック | 低（2-3日） |
| **シグナル生成** | 状態なし関数 | 低（1-2日） |
| **リスク管理** | 独立したロジック | 低（1日） |

#### 移植が複雑な部分 🟡

| 機能 | 課題 | 移植工数 |
|------|------|---------|
| **シグナル統合** | 履歴管理が必要 | 中（2-3日） |
| **バックテストエンジン** | vectorbt → 本番統合 | 中（3-4日） |

#### Phase 3.5が必須な部分 ❌

| 機能 | Phase 3.5依存理由 | 移植工数 |
|------|------------------|---------|
| **実トレード比較** | Position履歴不在 | 高（Phase 3.5後2日） |
| **シグナル精度評価** | 実績データなし | 高（Phase 3.5後2日） |

---

## 2. Phase 4: シグナル生成機能 詳細計画

### 2.1 実装ファイル構成

#### 新規作成ファイル（12ファイル）

##### Domain層（4ファイル）

| ファイル | 行数 | 内容 | Jupyter移植 |
|---------|------|------|-----------|
| `src/domain/entities/signal.py` | ~180行 | Signal Entity | ❌ 新規 |
| `src/domain/entities/integrated_signal.py` | ~120行 | 統合シグナルEntity | ❌ 新規 |
| `src/domain/services/signal_integration.py` | ~400行 | シグナル統合サービス | ✅ 投票システム移植 |
| `src/domain/repositories/signal_repository.py` | ~100行 | Signal Repository Interface | ❌ 新規 |

##### Application層（3ファイル）

| ファイル | 行数 | 内容 | Jupyter移植 |
|---------|------|------|-----------|
| `src/application/use_cases/signal_generation/generate_signals.py` | ~350行 | シグナル生成UseCase | ✅ 全シグナル統合 |
| `src/application/use_cases/signal_generation/signal_commands.py` | ~80行 | Command/Result DTO | ❌ 新規 |
| `src/application/use_cases/signal_generation/evaluate_signal_accuracy.py` | ~200行 | シグナル精度評価 | ❌ 新規（Phase 3.5後） |

##### Infrastructure層（5ファイル）

| ファイル | 行数 | 内容 | Jupyter移植 |
|---------|------|------|-----------|
| `src/infrastructure/gateways/analysis/technical_analysis_provider.py` | ~500行 | テクニカル分析Provider | ✅ Jupyter移植 |
| `src/infrastructure/gateways/analysis/support_resistance_analyzer.py` | ~300行 | S/R分析（DBSCAN） | ✅ Jupyter移植 |
| `src/infrastructure/gateways/analysis/trend_analyzer.py` | ~200行 | ダウ理論トレンド判定 | ✅ Jupyter移植 |
| `src/infrastructure/gateways/analysis/pivot_calculator.py` | ~150行 | ピボット計算 | ✅ Jupyter移植 |
| `src/infrastructure/persistence/dynamodb/dynamodb_signal_repository.py` | ~300行 | Signal Repository実装 | ❌ 新規 |

**合計**: 約2,880行（Jupyter移植: 約1,500行、新規: 約1,380行）

### 2.2 Signal Entity設計

```python
# src/domain/entities/signal.py
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Signal:
    """シグナルエンティティ
    
    Jupyterのシグナル生成器の出力を型安全にラップ
    """
    
    # アイデンティティ
    signal_id: str
    
    # 基本属性
    symbol: str
    timeframe: str
    signal_type: str    # BUY (1), SELL (-1), NEUTRAL (0)
    indicator_name: str # S/R, RSI, MACD, BB
    
    # シグナル詳細
    confidence: float   # 0.0-1.0
    strength: float     # 0.0-1.0（シグナルの強度）
    
    # エントリー情報（Optional: S/Rシグナルで設定）
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    
    # リスク・リワード
    risk_reward_ratio: Optional[float] = None
    
    # メタデータ
    generated_at: datetime
    expires_at: datetime  # シグナルの有効期限
    metadata: Dict[str, Any] = None
    
    def is_valid(self) -> bool:
        """有効性チェック"""
        return datetime.utcnow() < self.expires_at
    
    def is_buy(self) -> bool:
        return self.signal_type == 'BUY'
    
    def is_sell(self) -> bool:
        return self.signal_type == 'SELL'
    
    def calculate_risk_reward_ratio(self) -> Optional[float]:
        """RR比計算（Jupyterのロジック移植）"""
        if not (self.entry_price and self.stop_loss and self.take_profit):
            return None
        
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        
        if risk <= 0:
            return None
        
        return float(reward / risk)
```

### 2.3 SignalIntegrationService設計（Jupyter移植）

```python
# src/domain/services/signal_integration.py
from typing import List
from collections import Counter

class SignalIntegrationService:
    """シグナル統合ドメインサービス
    
    Jupyterの投票システムロジックを移植
    """
    
    def __init__(self, lookback_period: int = 5):
        """
        Args:
            lookback_period: 過去N本分のシグナルを考慮（Jupyter: SIGNAL_LOOKBACK_PERIOD）
        """
        self.lookback_period = lookback_period
    
    def integrate_signals(
        self, 
        signal_history: List[List[Signal]]
    ) -> IntegratedSignal:
        """複数シグナルの統合
        
        Jupyterのrun_backtest()の投票ロジックを移植:
        - 過去N本のシグナル履歴を集計
        - Buy/Sell別に投票
        - 2票以上でコンセンサス成立
        
        Args:
            signal_history: 過去N本分の全シグナル（各時点で4種類）
            
        Returns:
            IntegratedSignal: 統合シグナル（BUY/SELL/NEUTRAL）
        """
        # Jupyterの実装:
        # buy_votes = sum(1 for col in lookback_slice.columns 
        #                 if (lookback_slice[col] == 1).any())
        # sell_votes = sum(1 for col in lookback_slice.columns 
        #                  if (lookback_slice[col] == -1).any())
        
        buy_votes = 0
        sell_votes = 0
        
        # 過去N本分のシグナルを集計
        for signals_at_time in signal_history:
            for signal in signals_at_time:
                if signal.is_valid():
                    if signal.is_buy():
                        buy_votes += 1
                    elif signal.is_sell():
                        sell_votes += 1
        
        # 投票結果からコンセンサス決定（Jupyterと同じ閾値: 2票）
        consensus_type = 'NEUTRAL'
        if buy_votes >= 2:
            consensus_type = 'BUY'
        elif sell_votes >= 2:
            consensus_type = 'SELL'
        
        # 信頼度加重平均（全シグナルから計算）
        all_signals = [s for signals in signal_history for s in signals]
        weighted_confidence = self._calculate_weighted_confidence(all_signals)
        
        return IntegratedSignal(
            signal_type=consensus_type,
            confidence=weighted_confidence,
            buy_votes=buy_votes,
            sell_votes=sell_votes,
            component_signals=all_signals,
            generated_at=datetime.utcnow()
        )
    
    def _calculate_weighted_confidence(self, signals: List[Signal]) -> float:
        """信頼度加重平均"""
        valid_signals = [s for s in signals if s.is_valid()]
        if not valid_signals:
            return 0.0
        
        total_weight = sum(s.confidence for s in valid_signals)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            s.confidence * s.strength 
            for s in valid_signals
        )
        return weighted_sum / total_weight
```

### 2.4 TechnicalAnalysisProvider設計（Jupyter移植）

```python
# src/infrastructure/gateways/analysis/technical_analysis_provider.py
import talib
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import DBSCAN
from typing import Tuple, List, Dict, Any

class TechnicalAnalysisProvider:
    """テクニカル分析プロバイダー
    
    Jupyterの分析ロジックを本番システムに移植
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Jupyterのパラメータを移植
            {
                'ZONE_PEAK_DISTANCE': 5,
                'ZONE_EPS_MULTIPLIER': 0.001,
                'ZONE_MIN_SAMPLES': 2,
                'MA_PERIOD': 20,
                'ADX_PERIOD': 14,
                'ADX_STRONG_THRESHOLD': 25
            }
        """
        self.config = config
    
    def analyze_support_resistance(
        self, 
        ohlcv: pd.DataFrame
    ) -> Tuple[List[float], List[float], Dict[str, Any]]:
        """サポート/レジスタンス検出
        
        Jupyterのget_support_resistance()を完全移植
        
        Returns:
            supports: サポート価格リスト（降順）
            resistances: レジスタンス価格リスト（昇順）
            details: グラフ描画用詳細情報
        """
        # 1. スイングハイ/ロー検出（Jupyterと同じロジック）
        prominence_threshold = ohlcv['high'].std() * 0.3
        high_peaks, _ = find_peaks(
            ohlcv['high'], 
            distance=self.config['ZONE_PEAK_DISTANCE'], 
            prominence=prominence_threshold
        )
        low_peaks, _ = find_peaks(
            -ohlcv['low'], 
            distance=self.config['ZONE_PEAK_DISTANCE'], 
            prominence=prominence_threshold
        )
        
        sig_highs_df = ohlcv.iloc[high_peaks]
        sig_lows_df = ohlcv.iloc[low_peaks]
        
        # 2. DBSCAN クラスタリング（Jupyterと同じパラメータ）
        sig_points = pd.concat([
            sig_highs_df[['high']].rename(columns={'high': 'price'}),
            sig_lows_df[['low']].rename(columns={'low': 'price'})
        ])
        
        zones = []
        isolated_lines = pd.DataFrame()
        
        if len(sig_points) >= self.config['ZONE_MIN_SAMPLES']:
            prices = sig_points['price'].values.reshape(-1, 1)
            eps = ohlcv['high'].mean() * self.config['ZONE_EPS_MULTIPLIER']
            
            clustering = DBSCAN(
                eps=eps, 
                min_samples=self.config['ZONE_MIN_SAMPLES']
            ).fit(prices)
            
            sig_points['label'] = clustering.labels_
            
            # ゾーン形成
            for label in set(clustering.labels_):
                if label != -1:
                    zone_prices = sig_points[sig_points['label'] == label]['price']
                    zones.append({
                        'min': zone_prices.min(), 
                        'max': zone_prices.max()
                    })
            
            isolated_lines = sig_points[sig_points['label'] == -1]
        else:
            isolated_lines = sig_points
        
        # 3. サポート/レジスタンス分類（Jupyterと同じロジック）
        current_price = ohlcv['close'].iloc[-1]
        
        supports_raw = [z['max'] for z in zones if z['max'] < current_price] + \
                       [p for p in isolated_lines['price'] if p < current_price]
        
        resistances_raw = [z['min'] for z in zones if z['min'] > current_price] + \
                          [p for p in isolated_lines['price'] if p > current_price]
        
        supports = sorted(supports_raw, reverse=True)
        resistances = sorted(resistances_raw)
        
        # グラフ描画用詳細情報
        details = {
            "swing_highs": sig_highs_df,
            "swing_lows": sig_lows_df,
            "zones": zones
        }
        
        return supports, resistances, details
    
    def calculate_pivots(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """ピボットポイント計算
        
        Jupyterのcalculate_pivots()を完全移植
        """
        # データを日足にリサンプリング
        daily_df = ohlcv.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        # 前日データ
        prev_high = daily_df['high'].shift(1)
        prev_low = daily_df['low'].shift(1)
        prev_close = daily_df['close'].shift(1)
        
        # ピボット計算
        p = (prev_high + prev_low + prev_close) / 3
        r1 = 2 * p - prev_low
        s1 = 2 * p - prev_high
        r2 = p + (prev_high - prev_low)
        s2 = p - (prev_high - prev_low)
        
        pivots_daily = pd.concat([p, s1, r1, s2, r2], axis=1)
        pivots_daily.columns = ['P', 'S1', 'R1', 'S2', 'R2']
        
        # 元の時間足にマッピング
        pivots = pivots_daily.reindex(ohlcv.index, method='ffill')
        return pivots
    
    def analyze_trend(
        self, 
        ohlcv: pd.DataFrame
    ) -> Dict[str, str]:
        """トレンド分析
        
        Jupyterのget_trend_environment()を完全移植
        """
        # ダウ理論判定
        high_prominence = ohlcv['high'].std() * 0.2
        low_prominence = ohlcv['low'].std() * 0.2
        
        high_peaks, _ = find_peaks(
            ohlcv['high'], 
            distance=self.config.get('DOW_PEAK_DISTANCE', 5), 
            prominence=high_prominence
        )
        low_peaks, _ = find_peaks(
            -ohlcv['low'], 
            distance=self.config.get('DOW_PEAK_DISTANCE', 5), 
            prominence=low_prominence
        )
        
        recent_highs = ohlcv.iloc[high_peaks]['high'].tail(2)
        recent_lows = ohlcv.iloc[low_peaks]['low'].tail(2)
        
        is_uptrend_dow = (
            len(recent_highs) >= 2 and len(recent_lows) >= 2 and 
            recent_highs.iloc[-1] > recent_highs.iloc[-2] and 
            recent_lows.iloc[-1] > recent_lows.iloc[-2]
        )
        
        is_downtrend_dow = (
            len(recent_highs) >= 2 and len(recent_lows) >= 2 and 
            recent_highs.iloc[-1] < recent_highs.iloc[-2] and 
            recent_lows.iloc[-1] < recent_lows.iloc[-2]
        )
        
        # 移動平均フィルター
        ma = talib.SMA(ohlcv['close'], timeperiod=self.config['MA_PERIOD'])
        is_above_ma = ohlcv['close'].iloc[-1] > ma.iloc[-1]
        
        # ADX トレンド強度
        adx = talib.ADX(
            ohlcv['high'], 
            ohlcv['low'], 
            ohlcv['close'], 
            timeperiod=self.config['ADX_PERIOD']
        )
        
        trend_strength = "Weak/Ranging"
        if not pd.isna(adx.iloc[-1]) and adx.iloc[-1] > self.config['ADX_STRONG_THRESHOLD']:
            trend_strength = "Strong"
        
        # 最終判定
        trend_direction = "Range/Unclear"
        if is_uptrend_dow and is_above_ma:
            trend_direction = "Uptrend"
        elif is_downtrend_dow and not is_above_ma:
            trend_direction = "Downtrend"
        
        return {
            'direction': trend_direction,
            'strength': trend_strength
        }
```

### 2.5 シグナル生成UseCase設計

```python
# src/application/use_cases/signal_generation/generate_signals.py
class GenerateSignalsUseCase:
    """シグナル生成ユースケース
    
    Jupyterの全シグナル生成ロジックを統合
    """
    
    def __init__(
        self,
        technical_analysis_provider: TechnicalAnalysisProvider,
        signal_integration_service: SignalIntegrationService,
        signal_repository: ISignalRepository,
        ohlcv_data_provider: OhlcvDataProvider
    ):
        self.ta_provider = technical_analysis_provider
        self.signal_service = signal_integration_service
        self.signal_repo = signal_repository
        self.data_provider = ohlcv_data_provider
    
    def execute(self, command: GenerateSignalsCommand) -> GenerateSignalsResult:
        """シグナル生成実行
        
        Jupyterのget_all_signals_for_test()を拡張
        
        Args:
            command: {
                'symbol': 'USDJPY',
                'timeframe': 'M5',
                'candles': 500
            }
        """
        # 1. OHLCVデータ取得（過去N本）
        ohlcv = self.data_provider.get_ohlcv(
            symbol=command.symbol,
            timeframe=command.timeframe,
            limit=command.candles
        )
        
        # 2. テクニカル分析実行（Jupyter移植）
        supports, resistances, sr_details = self.ta_provider.analyze_support_resistance(ohlcv)
        pivots = self.ta_provider.calculate_pivots(ohlcv)
        trend = self.ta_provider.analyze_trend(ohlcv)
        
        # 3. 各シグナル生成（Jupyter移植）
        current_candle = ohlcv.iloc[-1]
        close_prices = ohlcv['close']
        
        signals = []
        
        # S/Rシグナル
        sr_signal = self._generate_sr_signal(
            current_candle, 
            supports, 
            resistances
        )
        if sr_signal:
            signals.append(sr_signal)
        
        # RSIシグナル
        rsi_signal = self._generate_rsi_signal(close_prices)
        if rsi_signal:
            signals.append(rsi_signal)
        
        # MACDシグナル
        macd_signal = self._generate_macd_signal(close_prices)
        if macd_signal:
            signals.append(macd_signal)
        
        # ボリンジャーバンドシグナル
        bb_signal = self._generate_bb_signal(close_prices)
        if bb_signal:
            signals.append(bb_signal)
        
        # 4. シグナル統合（Jupyter投票システム移植）
        signal_history = self._get_signal_history(
            command.symbol, 
            command.timeframe,
            lookback=5
        )
        signal_history.append(signals)
        
        integrated_signal = self.signal_service.integrate_signals(signal_history)
        
        # 5. シグナル保存
        for signal in signals:
            self.signal_repo.save(signal)
        
        return GenerateSignalsResult(
            signals=signals,
            integrated_signal=integrated_signal,
            trend=trend,
            supports=supports,
            resistances=resistances
        )
    
    def _generate_sr_signal(
        self, 
        current_candle, 
        supports, 
        resistances
    ) -> Optional[Signal]:
        """S/Rシグナル生成（Jupyter移植）"""
        # Jupyterのgenerate_sr_signal()と同じロジック
        ENTRY_BUFFER_PERCENT = 0.001
        
        # 買いシグナル：サポートに接触
        if supports:
            support_price = supports[0]
            entry_trigger = support_price * (1 + ENTRY_BUFFER_PERCENT)
            if current_candle['low'] <= entry_trigger:
                return Signal(
                    signal_id=f"SR-BUY-{uuid.uuid4()}",
                    symbol=current_candle.name,
                    timeframe='M5',
                    signal_type='BUY',
                    indicator_name='S/R',
                    confidence=0.8,
                    strength=0.9,
                    entry_price=Decimal(str(support_price)),
                    stop_loss=Decimal(str(support_price * 0.998)),
                    take_profit=Decimal(str(resistances[0])) if resistances else None,
                    generated_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=1)
                )
        
        # 売りシグナル：レジスタンスに接触
        if resistances:
            resistance_price = resistances[0]
            entry_trigger = resistance_price * (1 - ENTRY_BUFFER_PERCENT)
            if current_candle['high'] >= entry_trigger:
                return Signal(
                    signal_id=f"SR-SELL-{uuid.uuid4()}",
                    symbol=current_candle.name,
                    timeframe='M5',
                    signal_type='SELL',
                    indicator_name='S/R',
                    confidence=0.8,
                    strength=0.9,
                    entry_price=Decimal(str(resistance_price)),
                    stop_loss=Decimal(str(resistance_price * 1.002)),
                    take_profit=Decimal(str(supports[0])) if supports else None,
                    generated_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=1)
                )
        
        return None
    
    def _generate_rsi_signal(self, close_prices) -> Optional[Signal]:
        """RSIシグナル生成（Jupyter移植）"""
        # Jupyterのgenerate_rsi_signal()と同じロジック
        if len(close_prices) < 16:
            return None
        
        rsi = talib.RSI(close_prices, timeperiod=14)
        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        # 買いシグナル
        if prev_rsi <= 30 and last_rsi > 30:
            return Signal(
                signal_id=f"RSI-BUY-{uuid.uuid4()}",
                signal_type='BUY',
                indicator_name='RSI',
                confidence=0.7,
                strength=0.8,
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
        
        # 売りシグナル
        if prev_rsi >= 70 and last_rsi < 70:
            return Signal(
                signal_id=f"RSI-SELL-{uuid.uuid4()}",
                signal_type='SELL',
                indicator_name='RSI',
                confidence=0.7,
                strength=0.8,
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
        
        return None
    
    # _generate_macd_signal(), _generate_bb_signal() も同様に実装
```

### 2.6 Phase 4 実装スケジュール

#### Week 1: Domain & Infrastructure移植（5日間）

| Day | 作業 | 成果物 | 工数 |
|-----|------|-------|------|
| **Day 1** | Signal Entity実装 | signal.py, integrated_signal.py | 6時間 |
| **Day 2** | SignalIntegrationService実装（Jupyter移植） | signal_integration.py | 8時間 |
| **Day 3** | TechnicalAnalysisProvider実装（S/R, Pivot） | support_resistance_analyzer.py, pivot_calculator.py | 8時間 |
| **Day 4** | TrendAnalyzer実装（ダウ理論） | trend_analyzer.py, technical_analysis_provider.py | 8時間 |
| **Day 5** | Signal Repository実装 | dynamodb_signal_repository.py | 8時間 |

#### Week 2: Application層 & UI（2日間）

| Day | 作業 | 成果物 | 工数 |
|-----|------|-------|------|
| **Day 6** | GenerateSignalsUseCase実装 | generate_signals.py | 8時間 |
| **Day 7** | Streamlit UI統合 | signal_page.py | 8時間 |

**合計**: 7日間（54時間）

---

## 3. Phase 5: バックテスト機能 詳細計画

### 3.1 実装ファイル構成

#### 新規作成ファイル（7ファイル）

##### Domain層（3ファイル）

| ファイル | 行数 | 内容 | Jupyter移植 |
|---------|------|------|-----------|
| `src/domain/entities/backtest_result.py` | ~150行 | バックテスト結果Entity | ❌ 新規 |
| `src/domain/entities/trade.py` | ~120行 | Trade Entity | ❌ 新規 |
| `src/domain/services/backtest_engine.py` | ~500行 | バックテストエンジン | ✅ run_backtest()移植 |

##### Application層（2ファイル）

| ファイル | 行数 | 内容 | Phase 3.5依存 |
|---------|------|------|--------------|
| `src/application/use_cases/backtesting/run_backtest.py` | ~300行 | バックテスト実行 | ❌ なし |
| `src/application/use_cases/backtesting/compare_results.py` | ~250行 | 実トレード比較 | ✅ **Phase 3.5必須** |

##### Presentation層（2ファイル）

| ファイル | 行数 | 内容 | Phase 3.5依存 |
|---------|------|------|--------------|
| `src/presentation/ui/streamlit/pages/backtest_page.py` | ~600行 | バックテストUI | 🟡 部分的 |
| `src/presentation/ui/streamlit/components/backtest_charts.py` | ~400行 | グラフコンポーネント | ❌ なし |

**合計**: 約2,320行（Jupyter移植: 約500行、新規: 約1,820行）

### 3.2 BacktestEngine設計（Jupyter移植）

```python
# src/domain/services/backtest_engine.py
import vectorbt as vbt
from typing import List, Tuple
import pandas as pd

class BacktestEngine:
    """バックテストエンジン
    
    Jupyterのrun_backtest()を本番システムに移植
    """
    
    def __init__(
        self,
        signal_integration_service: SignalIntegrationService,
        technical_analysis_provider: TechnicalAnalysisProvider,
        config: Dict[str, Any]
    ):
        self.signal_service = signal_integration_service
        self.ta_provider = technical_analysis_provider
        self.config = config
    
    def run(
        self, 
        ohlcv: pd.DataFrame,
        strategy_config: Dict[str, Any]
    ) -> BacktestResult:
        """バックテスト実行
        
        Jupyterのrun_backtest()を完全移植
        
        Args:
            ohlcv: OHLCVデータ
            strategy_config: {
                'SIGNAL_LOOKBACK_PERIOD': 5,
                'RISK_REWARD_RATIO_THRESHOLD': 1.5,
                'TRAILING_STOP_ACTIVATION_RR': 1.5,
                'TRAILING_STOP_DISTANCE_RR': 1.5,
                'INITIAL_CAPITAL': 1_000_000,
                'ORDER_SIZE_USD': 100_000
            }
        """
        entries = pd.Series(False, index=ohlcv.index)
        exits = pd.Series(False, index=ohlcv.index)
        
        in_position = False
        active_trade = {}
        
        # シグナル履歴（Jupyter移植）
        signal_history = pd.DataFrame(
            index=ohlcv.index, 
            columns=['S/R', 'RSI', 'MACD', 'BB']
        ).fillna(0)
        
        # メインループ（Jupyter移植）
        for i in range(strategy_config['ANALYSIS_CANDLES'], len(ohlcv)):
            current_time = ohlcv.index[i]
            current_candle = ohlcv.iloc[i]
            
            # 決済ロジック（Jupyter移植）
            if in_position:
                is_closed, exit_reason = self._check_exit(
                    current_candle, 
                    active_trade,
                    strategy_config
                )
                
                if is_closed:
                    exits.iloc[i] = True
                    in_position = False
                    active_trade = {}
                continue
            
            # エントリーロジック（Jupyter移植）
            # 1. シグナル生成
            df_slice = ohlcv.iloc[:i].tail(strategy_config['ANALYSIS_CANDLES'])
            signals = self._generate_all_signals(df_slice, current_candle)
            signal_history.loc[current_time] = signals
            
            # 2. 投票システム（Jupyter移植）
            lookback_slice = signal_history.iloc[
                i - strategy_config['SIGNAL_LOOKBACK_PERIOD'] + 1 : i + 1
            ]
            
            buy_votes = sum(
                1 for col in lookback_slice.columns 
                if (lookback_slice[col] == 1).any()
            )
            sell_votes = sum(
                1 for col in lookback_slice.columns 
                if (lookback_slice[col] == -1).any()
            )
            
            # 3. エントリー判断（Jupyter移植）
            if buy_votes >= 2:
                trade_setup = self._build_buy_trade(
                    current_candle, 
                    df_slice, 
                    strategy_config
                )
                if trade_setup:
                    entries.iloc[i] = True
                    in_position = True
                    active_trade = trade_setup
            
            elif sell_votes >= 2:
                trade_setup = self._build_sell_trade(
                    current_candle, 
                    df_slice, 
                    strategy_config
                )
                if trade_setup:
                    entries.iloc[i] = True
                    in_position = True
                    active_trade = trade_setup
        
        # vectorbt統合（Jupyter移植）
        portfolio = vbt.Portfolio.from_signals(
            ohlcv['close'],
            entries=entries,
            exits=exits,
            init_cash=strategy_config['INITIAL_CAPITAL'],
            size=strategy_config['ORDER_SIZE_USD'],
            size_type='value'
        )
        
        return BacktestResult(
            portfolio=portfolio,
            trades=portfolio.trades.records,
            stats=portfolio.stats(),
            entries=entries,
            exits=exits
        )
    
    def _check_exit(
        self, 
        current_candle, 
        active_trade, 
        config
    ) -> Tuple[bool, str]:
        """決済チェック（Jupyter移植）"""
        sl_price = active_trade['sl']
        trade_type = active_trade['type']
        
        # Stop Loss
        if (trade_type == 'Buy' and current_candle['low'] <= sl_price) or \
           (trade_type == 'Sell' and current_candle['high'] >= sl_price):
            return True, "Stop Loss"
        
        # Fixed TP
        if active_trade['exit_mode'] == 'fixed':
            tp_price = active_trade['tp']
            if (trade_type == 'Buy' and current_candle['high'] >= tp_price) or \
               (trade_type == 'Sell' and current_candle['low'] <= tp_price):
                return True, "Take Profit"
        
        # Trailing Stop（Jupyter移植）
        elif active_trade['exit_mode'] == 'trailing':
            original_sl = sl_price
            if trade_type == 'Buy':
                new_sl = current_candle['high'] - active_trade['trailing_distance']
                if new_sl > original_sl:
                    active_trade['sl'] = new_sl
            elif trade_type == 'Sell':
                new_sl = current_candle['low'] + active_trade['trailing_distance']
                if new_sl < original_sl:
                    active_trade['sl'] = new_sl
        
        return False, ""
    
    def _build_buy_trade(
        self, 
        current_candle, 
        df_slice, 
        config
    ) -> Optional[Dict]:
        """買いトレード構築（Jupyter移植）"""
        # S/R分析
        supports, resistances, _ = self.ta_provider.analyze_support_resistance(df_slice)
        
        support_price = supports[0] if supports else current_candle['low']
        stop_loss = support_price * config['SL_BUY_FACTOR']
        risk = current_candle['close'] - stop_loss
        
        if risk <= 0:
            return None
        
        # Fixed TP判定（Jupyter移植）
        if resistances:
            take_profit = resistances[0]
            reward = take_profit - current_candle['close']
            
            if (reward / risk) >= config['RISK_REWARD_RATIO_THRESHOLD']:
                return {
                    'type': 'Buy',
                    'sl': stop_loss,
                    'tp': take_profit,
                    'exit_mode': 'fixed'
                }
        else:
            # Trailing Stop（Jupyter移植）
            trailing_distance = risk * config['TRAILING_STOP_DISTANCE_RR']
            return {
                'type': 'Buy',
                'sl': stop_loss,
                'trailing_distance': trailing_distance,
                'exit_mode': 'trailing'
            }
        
        return None
```

### 3.3 CompareBacktestVsRealUseCase設計（Phase 3.5必須）

```python
# src/application/use_cases/backtesting/compare_results.py
class CompareBacktestVsRealUseCase:
    """バックテスト vs 実トレード比較
    
    Phase 3.5完了後に実装可能
    """
    
    def __init__(
        self,
        position_repository: IPositionRepository,  # ← Phase 3.5必須
        backtest_engine: BacktestEngine
    ):
        self.position_repo = position_repository
        self.backtest_engine = backtest_engine
    
    def execute(
        self, 
        command: CompareBacktestCommand
    ) -> ComparisonReport:
        """比較実行
        
        Phase 3.5なしでは実行不可:
        - Position履歴がDynamoDBに存在しない
        - 実トレードデータが取得できない
        
        Args:
            command: {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'symbol': 'USDJPY',
                'strategy_config': {...}
            }
        """
        # 1. バックテスト実行
        backtest_result = self.backtest_engine.run(...)
        bt_metrics = self._calculate_metrics(backtest_result)
        
        # 2. 実トレード履歴取得（Phase 3.5必須）
        real_positions = self.position_repo.find_by_period(
            start=command.start_date,
            end=command.end_date,
            symbol=command.symbol
        )
        
        if not real_positions:
            raise NoRealTradeDataError(
                "Position履歴が存在しません。Phase 3.5の実装が必要です。"
            )
        
        real_metrics = self._calculate_real_metrics(real_positions)
        
        # 3. 比較分析
        return ComparisonReport(
            backtest_metrics=bt_metrics,
            real_metrics=real_metrics,
            slippage_analysis=self._analyze_slippage(backtest_result, real_positions),
            accuracy_delta=real_metrics.win_rate - bt_metrics.win_rate,
            recommendations=self._generate_recommendations(...)
        )
```

### 3.4 Phase 5 実装スケジュール

#### Phase 3.5完了前（3日間）

| Day | 作業 | 成果物 | Phase 3.5依存 |
|-----|------|-------|--------------|
| **Day 1** | BacktestEngine実装（Jupyter移植） | backtest_engine.py | ❌ なし |
| **Day 2** | BacktestResult Entity実装 | backtest_result.py, trade.py | ❌ なし |
| **Day 3** | RunBacktestUseCase実装 | run_backtest.py | ❌ なし |

#### Phase 3.5完了後（2日間）

| Day | 作業 | 成果物 | Phase 3.5依存 |
|-----|------|-------|--------------|
| **Day 4** | CompareBacktestVsRealUseCase実装 | compare_results.py | ✅ **必須** |
| **Day 5** | Streamlit UI統合（比較機能） | backtest_page.py拡張 | ✅ **必須** |

**合計**: 5日間（Phase 3.5完了前3日 + 完了後2日）

---

## 4. Phase 3.5との統合戦略

### 4.1 Phase 3.5完了前に実装可能な部分

#### Phase 4

```
✅ 実装可能:
- Signal Entity
- SignalIntegrationService（投票システム）
- TechnicalAnalysisProvider（全分析ロジック）
- GenerateSignalsUseCase（シグナル生成）
- Signal Repository（DynamoDB保存）
- Streamlit UI（シグナル表示）

❌ 制限される:
- シグナル精度評価（Position履歴不在）
- Signal-Position紐付け（監査証跡不完全）
```

#### Phase 5

```
✅ 実装可能:
- BacktestEngine（Jupyter移植）
- BacktestResult Entity
- RunBacktestUseCase
- Streamlit UI（バックテスト実行）

❌ 制限される:
- 実トレード vs バックテスト比較（Position履歴不在）
- システム評価（アーキテクチャ不整合）
```

### 4.2 Phase 3.5完了後の拡張

```python
# Phase 3.5完了後に追加実装

# 1. シグナル精度評価（Phase 4拡張）
class EvaluateSignalAccuracyUseCase:
    def execute(self, signal: Signal) -> SignalAccuracyReport:
        # Phase 3.5のPosition履歴を使用
        past_positions = self.position_repo.find_by_signal(signal.signal_id)
        
        accuracy = self._calculate_accuracy(past_positions)
        profitability = self._calculate_profitability(past_positions)
        
        return SignalAccuracyReport(
            signal=signal,
            accuracy=accuracy,
            profitability=profitability,
            sample_size=len(past_positions)
        )

# 2. 実トレード比較（Phase 5拡張）
class CompareBacktestVsRealUseCase:
    def execute(self, command: CompareBacktestCommand) -> ComparisonReport:
        # Phase 3.5のPosition履歴を使用
        real_positions = self.position_repo.find_by_period(...)
        
        # バックテスト vs 実トレード比較
        comparison = self._compare_metrics(backtest_result, real_positions)
        
        return ComparisonReport(
            backtest_win_rate=backtest_result.win_rate,
            real_win_rate=real_metrics.win_rate,
            slippage=comparison.avg_slippage,
            recommendations=self._generate_recommendations(comparison)
        )
```

---

## 5. 実装スケジュール

### 5.1 推奨実施順序

```
┌─────────────────────────────────────────┐
│  Phase 3.5（2-3日）                      │
│  - Position管理クリーンアーキテクチャ統合  │
│  - DynamoDB Position保存                 │
│  - 監査証跡完全化                         │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Phase 4（7日）                          │
│  - シグナル生成機能（Jupyter移植）        │
│  - Signal Entity/Repository             │
│  - Streamlit UI統合                      │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Phase 4拡張（2日）                      │
│  - シグナル精度評価 ← Phase 3.5活用      │
│  - Signal-Position紐付け                │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Phase 5（3日）                          │
│  - バックテストエンジン（Jupyter移植）    │
│  - RunBacktestUseCase                   │
│  - Streamlit UI統合                      │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Phase 5拡張（2日）                      │
│  - 実トレード比較 ← Phase 3.5活用        │
│  - システム評価                           │
└─────────────────────────────────────────┘

合計: 16-17日
```

### 5.2 総工数見積もり

| Phase | 基本実装 | Phase 3.5後拡張 | 合計 |
|-------|---------|----------------|------|
| **Phase 3.5** | 2-3日 | - | 2-3日 |
| **Phase 4** | 7日 | 2日 | 9日 |
| **Phase 5** | 3日 | 2日 | 5日 |
| **合計** | **12-13日** | **4日** | **16-17日** |

---

## 6. まとめ

### 6.1 既存実装の高完成度

✅ **SageMaker Jupyterバックテストコードは非常に完成度が高い**:
- 複数のテクニカル分析実装済み
- 投票システムによるシグナル統合
- リスク管理（RR比、トレーリングストップ）
- vectorbt統合
- 可視化完備

### 6.2 本番システムへの移植戦略

**移植容易性**:
- テクニカル分析: 純粋な計算 → 簡単に移植可能
- シグナル生成: 状態なし関数 → クリーンアーキテクチャに適合
- バックテストエンジン: vectorbt統合 → 本番でも使用可能

**Phase 3.5の重要性**:
- シグナル精度評価にPosition履歴が必須
- 実トレード vs バックテスト比較に必須
- アーキテクチャ統一が必須

### 6.3 最終推奨

**Phase 3.5 → Phase 4 → Phase 5 の順序で実施** ⭐⭐⭐

この順序により:
1. データ基盤が整う（Phase 3.5）
2. 高品質なシグナル生成（Phase 4 + Jupyter移植）
3. 完全なシステム評価（Phase 5 + 実トレード比較）

が実現できます。

---

**Document Version**: 1.0  
**Created**: 2026-01-13  
**Author**: Riki  
**Next Step**: Phase 3.5 Rev.2実装開始 → Phase 4, 5の段階的実装