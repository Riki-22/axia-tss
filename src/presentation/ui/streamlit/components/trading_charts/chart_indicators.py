# src/presentation/ui/streamlit/components/trading_charts/chart_indicators.py

import pandas as pd
import logging
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ドメイン層のインポート
try:
    from src.domain.services.technical_indicators.pattern_detectors.pinbar_detector import PinBarDetector
    from src.domain.services.technical_indicators.pattern_detectors.engulfing_detector import EngulfingDetector
    from src.domain.services.technical_indicators.level_detectors.support_resistance import SupportResistanceDetector
    from src.domain.services.technical_indicators.level_detectors.trend_channel import TrendChannelDetector
    INDICATORS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Technical indicators not available: {e}")
    INDICATORS_AVAILABLE = False


class ChartIndicators:
    """テクニカルインジケーター検出を担当するクラス"""
    
    def __init__(self, min_confidence: float = 0.6):
        """
        Args:
            min_confidence: 最小信頼度閾値
        """
        self.min_confidence = min_confidence
        self.indicators_available = INDICATORS_AVAILABLE
        
        if INDICATORS_AVAILABLE:
            self._initialize_detectors()
        else:
            logger.warning("Technical indicators are not available")
    
    def _initialize_detectors(self):
        """検出器の初期化"""
        try:
            self.pinbar_detector = PinBarDetector(min_confidence=self.min_confidence)
            self.engulfing_detector = EngulfingDetector(min_confidence=self.min_confidence)
            self.sr_detector = SupportResistanceDetector(window=20, min_touches=2)
            self.channel_detector = TrendChannelDetector(min_points=2, lookback_period=30)
            logger.info("All detectors initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize detectors: {e}")
            self.indicators_available = False
    
    def detect_all(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        すべてのインジケーターを検出
        
        Args:
            df: OHLCVデータ
        
        Returns:
            検出結果の辞書
        """
        if not self.indicators_available:
            return self._empty_results()
        
        results = {
            'patterns': self.detect_patterns(df),
            'levels': self.detect_levels(df),
            'channel': self.detect_channel(df),
            'summary': {}
        }
        
        # サマリー情報の追加
        results['summary'] = self._create_summary(results)
        
        return results
    
    def detect_patterns(self, df: pd.DataFrame) -> Dict[str, List]:
        """
        パターン検出を実行
        
        Args:
            df: OHLCVデータ
        
        Returns:
            検出されたパターンの辞書
        """
        if not self.indicators_available:
            return {'pinbars': [], 'engulfings': []}
        
        try:
            pinbars = self.pinbar_detector.detect(df)
            engulfings = self.engulfing_detector.detect(df)
            
            logger.info(f"Detected {len(pinbars)} pin bars, {len(engulfings)} engulfings")
            
            return {
                'pinbars': pinbars,
                'engulfings': engulfings
            }
        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return {'pinbars': [], 'engulfings': []}
    
    def detect_levels(self, df: pd.DataFrame) -> Dict[str, List]:
        """
        サポート/レジスタンス検出を実行
        
        Args:
            df: OHLCVデータ
        
        Returns:
            検出されたレベルの辞書
        """
        if not self.indicators_available:
            return {'support': [], 'resistance': []}
        
        try:
            support_levels, resistance_levels = self.sr_detector.detect(df)
            
            logger.info(f"Detected {len(support_levels)} support, {len(resistance_levels)} resistance")
            
            return {
                'support': support_levels,
                'resistance': resistance_levels
            }
        except Exception as e:
            logger.error(f"Level detection error: {e}")
            return {'support': [], 'resistance': []}
    
    def detect_channel(self, df: pd.DataFrame) -> Optional[Any]:
        """
        トレンドチャネル検出を実行
        
        Args:
            df: OHLCVデータ
        
        Returns:
            検出されたチャネル（なければNone）
        """
        if not self.indicators_available:
            return None
        
        try:
            channel = self.channel_detector.detect(df)
            
            if channel:
                logger.info(f"Channel detected: {channel.trend_direction} with width {channel.channel_width:.3f}")
            else:
                logger.info("No channel detected")
            
            return channel
        except Exception as e:
            logger.error(f"Channel detection error: {e}")
            return None
    
    def _create_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        検出結果のサマリーを作成
        
        Args:
            results: 検出結果
        
        Returns:
            サマリー情報
        """
        patterns = results.get('patterns', {})
        levels = results.get('levels', {})
        channel = results.get('channel')
        
        # Bullish/Bearishパターンの分類
        bullish_pinbars = []
        bearish_pinbars = []
        bullish_engulfings = []
        bearish_engulfings = []
        
        for pinbar in patterns.get('pinbars', []):
            if hasattr(pinbar, 'pattern_type'):
                if pinbar.pattern_type == 'bullish_pinbar':
                    bullish_pinbars.append(pinbar)
                else:
                    bearish_pinbars.append(pinbar)
        
        for engulfing in patterns.get('engulfings', []):
            if hasattr(engulfing, 'pattern_type'):
                if engulfing.pattern_type == 'bullish_engulfing':
                    bullish_engulfings.append(engulfing)
                else:
                    bearish_engulfings.append(engulfing)
        
        summary = {
            'total_patterns': len(patterns.get('pinbars', [])) + len(patterns.get('engulfings', [])),
            'bullish_signals': len(bullish_pinbars) + len(bullish_engulfings),
            'bearish_signals': len(bearish_pinbars) + len(bearish_engulfings),
            'support_levels': len(levels.get('support', [])),
            'resistance_levels': len(levels.get('resistance', [])),
            'channel_detected': channel is not None,
            'channel_direction': channel.trend_direction if channel else None,
            'channel_width': channel.channel_width if channel else None
        }
        
        # 分類したパターンも結果に追加
        patterns['bullish_pinbars'] = bullish_pinbars
        patterns['bearish_pinbars'] = bearish_pinbars
        patterns['bullish_engulfings'] = bullish_engulfings
        patterns['bearish_engulfings'] = bearish_engulfings
        
        return summary
    
    def _empty_results(self) -> Dict[str, Any]:
        """
        空の結果を返す
        
        Returns:
            空の検出結果
        """
        return {
            'patterns': {
                'pinbars': [],
                'engulfings': [],
                'bullish_pinbars': [],
                'bearish_pinbars': [],
                'bullish_engulfings': [],
                'bearish_engulfings': []
            },
            'levels': {
                'support': [],
                'resistance': []
            },
            'channel': None,
            'summary': {
                'total_patterns': 0,
                'bullish_signals': 0,
                'bearish_signals': 0,
                'support_levels': 0,
                'resistance_levels': 0,
                'channel_detected': False,
                'channel_direction': None,
                'channel_width': None
            }
        }
    
    def get_detection_status(self) -> Dict[str, bool]:
        """
        各検出器のステータスを取得
        
        Returns:
            検出器の利用可能状態
        """
        if not self.indicators_available:
            return {
                'pinbar': False,
                'engulfing': False,
                'support_resistance': False,
                'trend_channel': False
            }
        
        return {
            'pinbar': hasattr(self, 'pinbar_detector'),
            'engulfing': hasattr(self, 'engulfing_detector'),
            'support_resistance': hasattr(self, 'sr_detector'),
            'trend_channel': hasattr(self, 'channel_detector')
        }