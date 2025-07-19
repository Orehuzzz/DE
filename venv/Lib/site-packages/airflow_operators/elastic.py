import json
from datetime import datetime
from typing import Any, Callable, Iterable

from airflow.hooks.base import BaseHook
from airflow.models import TaskInstance
from airflow.operators.python import PythonOperator
from elasticsearch import Elasticsearch


def chunks(lst, n) -> Iterable[list]:
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


class ElasticsearchCustomHook(BaseHook):
    conn_name_attr = "elasticsearch_conn_id"
    default_conn_name = "elasticsearch_default"
    conn_type = "elasticsearch_custom"
    hook_name = "ElasticsearchCustom"

    def __init__(self, conn_id: str):
        super().__init__()
        self.conn_id = conn_id

    def get_conn(self) -> Any:
        conn = self.get_connection(self.conn_id)
        hosts = [f'https://{conn.host}:{conn.port}']
        api_key = conn.get_password()

        client = Elasticsearch(hosts=hosts, api_key=api_key, **conn.extra_dejson)
        return client


class ElasticsearchBulkOperator(PythonOperator):
    """Выполняет bulk, формируемый в python_callable"""

    CHUNK_SIZE = 100

    def __init__(
        self,
        conn_id: str,
        index_name: str,
        python_callable: Callable,
        *args,
        **kwargs,
    ):
        super().__init__(*args, python_callable=python_callable, **kwargs)
        self.conn_id = conn_id
        self.index_name = index_name

    def execute_callable(self):
        hook = ElasticsearchCustomHook(self.conn_id)

        with hook.get_conn() as conn:
            bulk = self.python_callable(
                *self.op_args,
                **self.op_kwargs,
            )

            if bulk:
                for chunk in chunks(bulk, self.CHUNK_SIZE * 2):
                    result = conn.bulk(index=self.index_name, body=chunk)
                    self.check_errors(result)
            else:
                print("No data")

    @staticmethod
    def check_errors(result):
        if result["errors"]:
            errors = []

            for item in result["items"]:
                operation = next(iter(item))

                error_info = item[operation].get("error")

                if error_info and error_info.get("type") != "document_missing_exception":
                    errors.append(
                        {"operation": operation, "id": item[operation]["_id"], "error": error_info}
                    )
            if errors:
                raise ValueError(f"Bulk operation failed with errors: {errors}")


class ElasticSaveOperator(ElasticsearchBulkOperator):

    def __init__(
        self,
        conn_id: str,
        xcom_key: str,
        index_name: str,
        updated_prefix=None,
        is_upsert: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(
            conn_id=conn_id,
            index_name=index_name,
            python_callable=self.create_bulk,
            *args,
            **kwargs,
        )

        self.xcom_key = xcom_key
        self.updated_prefix = updated_prefix
        self.is_upsert = is_upsert

    def create_bulk(self, ti: TaskInstance) -> list[dict]:
        bulk = []
        item_jsons = ti.xcom_pull(key=self.xcom_key)

        for item_json in item_jsons:
            item = json.loads(item_json)
            _id = item.pop("_id")

            updated_key = (
                f"{self.updated_prefix if self.updated_prefix else ''}updated_at"
            )
            item[updated_key] = datetime.now().isoformat()

            bulk.append({"update": {"_id": _id}})
            bulk.append({"doc": item, "doc_as_upsert": self.is_upsert})

        return bulk
