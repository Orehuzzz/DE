import json
from typing import List

import redis
from airflow.providers.redis.hooks.redis import RedisHook


class RedisBase:
    def __init__(self, redis_conn_id: str, redis_collection_name: str):
        self._redis_hook = RedisHook(redis_conn_id)
        self.redis_collection_name = redis_collection_name
        self.redis_conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        if not self.redis_conn:
            self.redis_conn = self._redis_hook.get_conn()

    def close(self):
        if self.redis_conn:
            self.redis_conn.close()
            self.redis_conn = None


class OgrnRedisChecker(RedisBase):
    def is_ogrn_exists(self, ogrn: int) -> bool:
        """Проверяет наличие ОГРН в Redis множестве"""
        if not self.redis_conn:
            self.connect()

        try:
            return self.redis_conn.sismember(self.redis_collection_name, ogrn)
        except redis.ConnectionError:
            self.connect()  # Переподключение при ошибке
            return self.redis_conn.sismember(self.redis_collection_name, ogrn)


class CrossingInnOgrnRedisChecker(RedisBase):
    def get_ogrns_by_inn(self, inn: str) -> List[int]:
        if not self.redis_conn:
            self.connect()

        ogrns_str = self.redis_conn.hget(self.redis_collection_name, inn)
        ogrns = json.loads(ogrns_str) if ogrns_str else list()
        return ogrns
