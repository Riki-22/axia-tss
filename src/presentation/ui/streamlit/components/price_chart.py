# src/presentation/ui/streamlit/components/price_chart.py

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class PriceChartComponent:
    """価格チャート表示コンポーネント"""
    
    @staticmethod
    def render_chart(symbol="USDJPY", timeframe="H4", days=30):
        """インタラクティブな価格チャートを描画"""
        
        # ダミーデータ生成（後でS3から実データに置き換え）
        df = PriceChartComponent._generate_dummy_data(days)
        
        # Plotlyチャート作成
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.15, 0.15],
            subplot_titles=(f'{symbol} - {timeframe}', 'Volume', 'RSI')
        )
        
        # ローソク足チャート
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='OHLC',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ),
            row=1, col=1
        )
        
        # 移動平均線
        for ma_period, color in [(20, 'yellow'), (50, 'orange'), (200, 'purple')]:
            ma_col = f'MA{ma_period}'
            df[ma_col] = df['close'].rolling(window=ma_period).mean()
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[ma_col],
                    name=ma_col,
                    line=dict(color=color, width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )
        
        # ボリンジャーバンド
        bb_period = 20
        bb_std = 2
        df['BB_middle'] = df['close'].rolling(window=bb_period).mean()
        df['BB_std'] = df['close'].rolling(window=bb_period).std()
        df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * bb_std)
        df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * bb_std)
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['BB_upper'],
                name='BB Upper',
                line=dict(color='rgba(250,128,114,0.3)', width=1),
                showlegend=False
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['BB_lower'],
                name='BB Lower',
                line=dict(color='rgba(250,128,114,0.3)', width=1),
                fill='tonexty',
                fillcolor='rgba(250,128,114,0.1)',
                showlegend=False
            ),
            row=1, col=1
        )
        
        # ボリューム
        colors = ['#26a69a' if row['close'] >= row['open'] else '#ef5350' 
                  for _, row in df.iterrows()]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False
            ),
            row=2, col=1
        )
        
        # RSI
        df['RSI'] = PriceChartComponent._calculate_rsi(df['close'])
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['RSI'],
                name='RSI',
                line=dict(color='#ff9800', width=2)
            ),
            row=3, col=1
        )
        
        # RSI基準線
        fig.add_hline(y=70, line_dash="dash", line_color="red", 
                     opacity=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", 
                     opacity=0.5, row=3, col=1)
        
        # レイアウト設定
        fig.update_layout(
            template='plotly_dark',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            hovermode='x unified',
            xaxis_rangeslider_visible=False
        )
        
        # X軸の範囲選択ボタン
        fig.update_xaxes(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(step="all", label="ALL")
                ])
            ),
            row=1, col=1
        )
        
        return fig
    
    @staticmethod
    def _generate_dummy_data(days=30):
        """ダミーの価格データを生成"""
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
        
        # ランダムウォークで価格を生成
        np.random.seed(42)
        close_prices = 150 + np.cumsum(np.random.randn(len(dates)) * 0.1)
        
        data = []
        for i, date in enumerate(dates):
            close = close_prices[i]
            open_price = close + np.random.uniform(-0.1, 0.1)
            high = max(open_price, close) + abs(np.random.uniform(0, 0.2))
            low = min(open_price, close) - abs(np.random.uniform(0, 0.2))
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'datetime': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        return df
    
    @staticmethod
    def _calculate_rsi(prices, period=14):
        """RSIを計算"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi