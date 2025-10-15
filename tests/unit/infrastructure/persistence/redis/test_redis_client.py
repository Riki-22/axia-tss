# tests/unit/infrastructure/persistence/redis/test_redis_client.py
"""RedisClient 単体テスト"""

import pytest
import time
from src.infrastructure.persistence.redis import RedisClient
from src.infrastructure.config.settings import settings


class TestRedisClient:
    """RedisClient のテストクラス"""
    
    @classmethod
    def setup_class(cls):
        """テストクラス全体のセットアップ"""
        # シングルトンをリセット
        RedisClient.reset_instance()
    
    def teardown_method(self):
        """各テストメソッド後のクリーンアップ"""
        # テストキーを削除
        client = RedisClient.get_instance()
        test_keys = client.keys("test:*")
        if test_keys:
            client.delete(*test_keys)
    
    def test_singleton_pattern(self):
        """シングルトンパターンのテスト"""
        client1 = RedisClient.get_instance(
            host=settings.redis_endpoint,
            port=settings.redis_port,
            db=settings.redis_db
        )
        client2 = RedisClient.get_instance()
        
        assert client1 is client2, "シングルトンインスタンスが同一でない"
    
    def test_connection(self):
        """接続テスト"""
        client = RedisClient.get_instance(
            host=settings.redis_endpoint,
            port=settings.redis_port,
            db=settings.redis_db
        )
        
        assert client.ping() is True, "Redis接続に失敗"
    
    def test_set_get(self):
        """SET/GET操作のテスト"""
        client = RedisClient.get_instance()
        
        key = "test:set_get"
        value = b"test_value"
        
        # SET
        assert client.set(key, value, ex=60) is True
        
        # GET
        retrieved = client.get(key)
        assert retrieved == value
    
    def test_set_with_ttl(self):
        """TTL付きSETのテスト"""
        client = RedisClient.get_instance()
        
        key = "test:ttl"
        value = b"test_value"
        ttl_seconds = 5
        
        # TTL付きでSET
        client.set(key, value, ex=ttl_seconds)
        
        # TTL確認
        ttl = client.ttl(key)
        assert 0 < ttl <= ttl_seconds
        
        # データ確認
        assert client.get(key) == value
    
    def test_delete(self):
        """DELETE操作のテスト"""
        client = RedisClient.get_instance()
        
        key = "test:delete"
        value = b"test_value"
        
        # データ作成
        client.set(key, value, ex=60)
        assert client.exists(key) == 1
        
        # 削除
        deleted = client.delete(key)
        assert deleted == 1
        assert client.exists(key) == 0
    
    def test_exists(self):
        """EXISTS操作のテスト"""
        client = RedisClient.get_instance()
        
        key = "test:exists"
        
        # 存在しない
        assert client.exists(key) == 0
        
        # 作成
        client.set(key, b"value", ex=60)
        
        # 存在する
        assert client.exists(key) == 1
    
    def test_keys_pattern_match(self):
        """KEYSパターンマッチのテスト"""
        client = RedisClient.get_instance()
        
        # テストデータ作成
        test_data = {
            "test:pattern:1": b"value1",
            "test:pattern:2": b"value2",
            "test:other:1": b"value3"
        }
        
        for key, value in test_data.items():
            client.set(key, value, ex=60)
        
        # パターンマッチ
        pattern_keys = client.keys("test:pattern:*")
        assert len(pattern_keys) == 2
        assert "test:pattern:1" in pattern_keys
        assert "test:pattern:2" in pattern_keys
        assert "test:other:1" not in pattern_keys
    
    def test_expire(self):
        """EXPIRE操作のテスト"""
        client = RedisClient.get_instance()
        
        key = "test:expire"
        value = b"test_value"
        
        # データ作成（TTLなし）
        client.set(key, value)
        assert client.ttl(key) == -1  # TTL未設定
        
        # TTL設定
        assert client.expire(key, 10) is True
        
        # TTL確認
        ttl = client.ttl(key)
        assert 0 < ttl <= 10
    
    def test_multiple_operations(self):
        """複数操作の統合テスト"""
        client = RedisClient.get_instance()
        
        # 複数キー作成
        keys = [f"test:multi:{i}" for i in range(5)]
        for key in keys:
            client.set(key, f"value_{key}".encode(), ex=60)
        
        # EXISTS（複数キー）
        assert client.exists(*keys) == 5
        
        # DELETE（複数キー）
        deleted = client.delete(*keys)
        assert deleted == 5
        
        # 削除確認
        assert client.exists(*keys) == 0
    
    def test_info(self):
        """INFO操作のテスト"""
        client = RedisClient.get_instance()
        
        info = client.info("memory")
        
        assert isinstance(info, dict)
        assert "used_memory" in info
        assert info["used_memory"] > 0


class TestRedisClientErrorHandling:
    """RedisClient エラーハンドリングのテスト"""
    
    def test_get_nonexistent_key(self):
        """存在しないキーのGET"""
        client = RedisClient.get_instance()
        
        result = client.get("test:nonexistent")
        assert result is None
    
    def test_ttl_nonexistent_key(self):
        """存在しないキーのTTL"""
        client = RedisClient.get_instance()
        
        ttl = client.ttl("test:nonexistent")
        assert ttl == -2  # キーが存在しない
    
    def test_delete_nonexistent_key(self):
        """存在しないキーのDELETE"""
        client = RedisClient.get_instance()
        
        deleted = client.delete("test:nonexistent")
        assert deleted == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])