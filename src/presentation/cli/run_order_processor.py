# src/presentation/cli/run_order_processor.py
#!/usr/bin/env python
"""Order Manager のエントリーポイント"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.settings import settings
from src.infrastructure.di.container import container
from src.infrastructure.gateways.messaging.sqs.queue_listener import SQSQueueListener
from src.application.use_cases.order_processing.process_sqs_order import ProcessSQSOrderUseCase

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """メインエントリーポイント"""
    try:
        logger.info("=" * 60)
        logger.info("Order Manager 起動中...")
        logger.info("=" * 60)
        
        # 依存関係の取得
        kill_switch_repo = container.get_kill_switch_repository()
        mt5_connection = container.get_mt5_connection()
        mt5_order_executor = container.get_mt5_order_executor()
        
        # ユースケース作成
        process_order_use_case = ProcessSQSOrderUseCase(
            kill_switch_repository=kill_switch_repo,
            mt5_connection=mt5_connection,
            mt5_order_executor=mt5_order_executor,
            settings=settings
        )
        
        # SQSリスナー起動
        listener = SQSQueueListener(
            queue_url=settings.queue_url,
            sqs_client=settings.sqs_client,
            process_message_handler=process_order_use_case.execute
        )
        
        # ポーリング開始
        listener.start_polling()
        
    except KeyboardInterrupt:
        logger.info("\nOrder Manager を停止します...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"起動時エラー: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()