# src/infrastructure/persistence/dynamodb/dynamodb_position_repository.py

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.domain.entities.position import Position
from src.domain.repositories.position_repository import IPositionRepository

logger = logging.getLogger(__name__)


class DynamoDBPositionRepository(IPositionRepository):
    """ポジション管理のDynamoDBリポジトリ実装"""
    
    def __init__(self, table_name: str, dynamodb_resource):
        """
        初期化
        
        Args:
            table_name: DynamoDBテーブル名
            dynamodb_resource: boto3 DynamoDBリソース
        """
        self.table_name = table_name
        self.dynamodb_resource = dynamodb_resource
        self.table = dynamodb_resource.Table(table_name) if dynamodb_resource else None
        logger.info(f"DynamoDBPositionRepository initialized: table={table_name}")
    
    def save(self, position: Position) -> bool:
        """ポジションを保存"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return False
            
            item = position.to_dict()
            
            # 楽観的ロック（version属性追加）
            current_time = datetime.now(timezone.utc).isoformat()
            item['version'] = 1  # 新規作成時は1
            item['last_updated_utc'] = current_time
            
            self.table.put_item(Item=item)
            
            logger.info(
                f"Position saved: {position.position_id} "
                f"(MT5: {position.mt5_ticket}, {position.symbol} {position.side})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to save position {position.position_id}: {e}")
            return False
    
    def find_by_mt5_ticket(self, mt5_ticket: int) -> Optional[Position]:
        """MT5チケット番号でポジションを検索"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return None
            
            response = self.table.get_item(
                Key={
                    'pk': f'POSITION#{mt5_ticket}',
                    'sk': 'METADATA'
                }
            )
            
            item = response.get('Item')
            if item:
                logger.debug(f"Position found by MT5 ticket: {mt5_ticket}")
                return Position.from_dict(item)
            else:
                logger.debug(f"Position not found by MT5 ticket: {mt5_ticket}")
                return None
                
        except Exception as e:
            logger.error(f"Error finding position by MT5 ticket {mt5_ticket}: {e}")
            return None
    
    def find_by_position_id(self, position_id: str) -> Optional[Position]:
        """ポジションIDでポジションを検索"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return None
            
            # position_idでの検索は非効率（フルスキャン必要）
            # 通常はMT5チケット番号での検索を推奨
            response = self.table.scan(
                FilterExpression=Attr('position_id').eq(position_id),
                Limit=1
            )
            
            items = response.get('Items', [])
            if items:
                logger.debug(f"Position found by position ID: {position_id}")
                return Position.from_dict(items[0])
            else:
                logger.debug(f"Position not found by position ID: {position_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error finding position by position ID {position_id}: {e}")
            return None
    
    def find_open_positions(self, symbol: str = None) -> List[Position]:
        """オープンポジションを検索（GSI1活用）"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return []
            
            # GSI1を使用してOPENポジションを高速取得
            if symbol:
                # 特定シンボルのOPENポジション
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('gs1pk').eq('OPEN_POSITIONS') & 
                                         Key('gs1sk').begins_with(f'SYMBOL#{symbol}#')
                )
            else:
                # 全OPENポジション
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('gs1pk').eq('OPEN_POSITIONS')
                )
            
            items = response.get('Items', [])
            positions = []
            
            for item in items:
                try:
                    position = Position.from_dict(item)
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Failed to parse position item: {e}")
                    continue
            
            symbol_filter = f" for {symbol}" if symbol else ""
            logger.info(f"Found {len(positions)} open positions{symbol_filter}")
            
            return positions
            
        except Exception as e:
            logger.error(f"Error finding open positions: {e}")
            return []
    
    def find_closed_positions(self, symbol: str = None, limit: int = 100) -> List[Position]:
        """決済済みポジションを検索"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return []
            
            # CLOSEDポジションはGSI1に含まれないため、フィルターでスキャン
            filter_expression = Attr('status').eq('CLOSED')
            
            if symbol:
                filter_expression = filter_expression & Attr('symbol').eq(symbol)
            
            response = self.table.scan(
                FilterExpression=filter_expression,
                Limit=limit
            )
            
            items = response.get('Items', [])
            positions = []
            
            for item in items:
                try:
                    position = Position.from_dict(item)
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Failed to parse closed position item: {e}")
                    continue
            
            # 決済日時順（新しい順）でソート
            positions.sort(key=lambda p: p.closed_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            
            symbol_filter = f" for {symbol}" if symbol else ""
            logger.info(f"Found {len(positions)} closed positions{symbol_filter}")
            
            return positions
            
        except Exception as e:
            logger.error(f"Error finding closed positions: {e}")
            return []
    
    def update_status(
        self, 
        mt5_ticket: int, 
        status: str, 
        close_data: Optional[dict] = None
    ) -> bool:
        """ポジションステータスを更新"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return False
            
            # 現在のアイテム取得
            current_response = self.table.get_item(
                Key={
                    'pk': f'POSITION#{mt5_ticket}',
                    'sk': 'METADATA'
                }
            )
            
            current_item = current_response.get('Item')
            if not current_item:
                logger.warning(f"Position not found for status update: MT5 ticket {mt5_ticket}")
                return False
            
            current_version = current_item.get('version', 0)
            
            # 更新式作成
            update_expression = "SET #status = :status, #version = :new_version, last_updated_utc = :updated"
            expression_attribute_names = {
                '#status': 'status',
                '#version': 'version'
            }
            expression_attribute_values = {
                ':status': status,
                ':new_version': current_version + 1,
                ':updated': datetime.now(timezone.utc).isoformat(),
                ':current_version': current_version
            }
            
            # 決済データがある場合は追加
            if close_data:
                update_expression += ", closed_at = :closed_at, realized_pnl = :realized_pnl"
                expression_attribute_values.update({
                    ':closed_at': close_data.get('closed_at'),
                    ':realized_pnl': close_data.get('realized_pnl')
                })
                
                # CLOSEDの場合はGSI1から削除（スパースインデックス）
                if status == 'CLOSED':
                    update_expression += " REMOVE gs1pk, gs1sk"
            
            # 楽観的ロック付き更新
            self.table.update_item(
                Key={
                    'pk': f'POSITION#{mt5_ticket}',
                    'sk': 'METADATA'
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression='version = :current_version'
            )
            
            logger.info(f"Position status updated: MT5 ticket {mt5_ticket} -> {status}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Optimistic lock conflict for position {mt5_ticket}")
            else:
                logger.error(f"Failed to update position status {mt5_ticket}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating position status {mt5_ticket}: {e}")
            return False
    
    def delete_by_mt5_ticket(self, mt5_ticket: int) -> bool:
        """MT5チケット番号でポジションを削除"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return False
            
            self.table.delete_item(
                Key={
                    'pk': f'POSITION#{mt5_ticket}',
                    'sk': 'METADATA'
                }
            )
            
            logger.info(f"Position deleted: MT5 ticket {mt5_ticket}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete position {mt5_ticket}: {e}")
            return False
    
    def get_position_statistics(self, symbol: str = None) -> dict:
        """ポジション統計情報を取得"""
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return {
                    'total_positions': 0,
                    'open_positions': 0,
                    'closed_positions': 0,
                    'total_unrealized_pnl': 0,
                    'total_realized_pnl': 0
                }
            
            # オープンポジション統計（GSI1使用）
            open_positions = self.find_open_positions(symbol)
            
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in open_positions)
            
            # 決済済みポジション統計（最近100件）
            closed_positions = self.find_closed_positions(symbol, limit=100)
            
            total_realized_pnl = sum(
                pos.realized_pnl for pos in closed_positions 
                if pos.realized_pnl is not None
            )
            
            statistics = {
                'total_positions': len(open_positions) + len(closed_positions),
                'open_positions': len(open_positions),
                'closed_positions': len(closed_positions),
                'total_unrealized_pnl': float(total_unrealized_pnl),
                'total_realized_pnl': float(total_realized_pnl)
            }
            
            symbol_filter = f" for {symbol}" if symbol else ""
            logger.debug(f"Position statistics calculated{symbol_filter}: {statistics}")
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error calculating position statistics: {e}")
            return {
                'total_positions': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'total_unrealized_pnl': 0,
                'total_realized_pnl': 0
            }