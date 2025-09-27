# scripts/forex_tester_importer/forex_tester_parser.py
import pandas as pd
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

# ロギング設定
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(f"forex_tester_parser.{__name__}")

def parse_forex_tester_timestamp(dt_yyyymmdd_str: str, time_field: int, timeframe_str: str) -> Optional[datetime]:
    """
    ForexTester6の<DTYYYYMMDD>と<TIME>フィールド、および時間軸文字列から
    UTCのdatetimeオブジェクトを生成する。（既存のロジックをベースに改善）
    """
    try:
        base_date = datetime.strptime(str(dt_yyyymmdd_str), '%Y%m%d').replace(tzinfo=timezone.utc)
        
        tf_upper = timeframe_str.upper()
        hour, minute = 0, 0

        # M1,M5は経過分数、M15以上はHHMM形式という既存のロジックを適用
        if tf_upper in ["M1", "M5"]:
            total_minutes = int(time_field)
            hour = total_minutes // 60
            minute = total_minutes % 60
        else: # M15, M30, H1, H4, D1, W1, MN1
            time_field_int = int(time_field)
            hour = time_field_int // 100
            minute = time_field_int % 100
        
        # 日付またぎの処理
        if hour >= 24:
            days_to_add = hour // 24
            hour = hour % 24
            base_date += timedelta(days=days_to_add)

        return base_date + timedelta(hours=hour, minutes=minute)

    except (ValueError, TypeError) as e:
        logger.debug(f"Timestamp parse error: {e}. DateStr: {dt_yyyymmdd_str}, Time: {time_field}")
        return None

def parse_forex_tester_csv_to_golden_schema(file_path: str, timeframe_str: str) -> Optional[pd.DataFrame]:
    """
    Forex Tester CSV/TXTを読み込み、Golden Schemaに準拠したDataFrameに変換する。
    """
    logger.info(f"Parsing file: {file_path}")
    try:
        # 堅牢なCSV読み込み
        column_names = ['ticker', 'dtyyyymmdd', 'time', 'open', 'high', 'low', 'close', 'volume']
        df = pd.read_csv(
            file_path,
            delimiter='[\t,]', # タブとカンマの両方を区切り文字として許容
            header=None,
            names=column_names,
            on_bad_lines='skip',
            encoding='utf-8-sig',
            engine='python',
            dtype=str
        )
        
        if str(df.iloc[0]['ticker']).strip().upper() == '<TICKER>':
            df = df.iloc[1:].reset_index(drop=True)

        if df.empty:
            logger.warning(f"No valid data rows found in {file_path}")
            return None

        # --- Golden Schemaへの変換 ---
        df['timestamp_utc'] = df.apply(
            lambda row: parse_forex_tester_timestamp(row['dtyyyymmdd'], row['time'], timeframe_str), 
            axis=1
        )
        df.dropna(subset=['timestamp_utc'], inplace=True) # タイムスタンプのパース失敗行を削除

        ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in ohlcv_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=ohlcv_cols, inplace=True) # 数値変換失敗行を削除
        
        golden_schema_cols = ['timestamp_utc', 'open', 'high', 'low', 'close', 'volume']
        df_golden = df[golden_schema_cols].copy()
        
        df_golden = df_golden.astype({
            'open': 'float64', 'high': 'float64', 'low': 'float64', 'close': 'float64',
            'volume': 'int64'
        })
        
        df_golden = df_golden.sort_values(by='timestamp_utc').reset_index(drop=True)

        logger.info(f"Successfully parsed and conformed {len(df_golden)} rows from {file_path}.")
        return df_golden
        
    except Exception as e:
        logger.error(f"Failed to parse file {file_path}: {e}", exc_info=True)
        return None