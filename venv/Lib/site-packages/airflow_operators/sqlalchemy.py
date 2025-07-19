import json
from datetime import datetime
from typing import Callable

from airflow.models import TaskInstance
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook
from sqlalchemy import update, delete, and_
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import sessionmaker, DeclarativeMeta, Session

from airflow_operators.utils.importer import import_from_string


class SQLAlchemySessionOperator(PythonOperator):
    def __init__(
            self, conn_id: str, python_callable: Callable, *args, **kwargs
    ):
        super().__init__(*args, python_callable=python_callable, **kwargs)
        self.conn_id = conn_id

    def get_session_factory(self) -> sessionmaker:
        hook = MySqlHook(self.conn_id)
        engine = hook.get_sqlalchemy_engine()

        return sessionmaker(bind=engine)

    def execute_callable(self):
        session_factory = self.get_session_factory()

        with session_factory() as session:
            try:
                result = self.python_callable(
                    *self.op_args, session=session, **self.op_kwargs
                )
            except Exception:
                session.rollback()
                raise
            else:
                session.commit()
        return result


class MergeOrmOperator(SQLAlchemySessionOperator):

    def __init__(
            self,
            conn_id: str,
            xcom_key: str,
            orm_model: DeclarativeMeta | str,
            *args,
            **kwargs,
    ):
        super().__init__(
            conn_id=conn_id,
            python_callable=self.save,
            *args,
            **kwargs,
        )

        self.xcom_key = xcom_key
        self.orm_model = (
            import_from_string(orm_model) if isinstance(orm_model, str) else orm_model
        )

    def save(self, session: Session, ti: TaskInstance):
        import json
        from airflow_operators.utils.orm_converter import OrmConverter

        org_jsons = ti.xcom_pull(key=self.xcom_key)

        for org_json in org_jsons:
            org_data = json.loads(org_json)
            organization = OrmConverter.convert_tree_to_orm(org_data, self.orm_model)
            session.merge(organization)


class OrmMergeOperator(MergeOrmOperator):
    ...


class UpdateOrmOperator(SQLAlchemySessionOperator):

    def __init__(
            self,
            conn_id: str,
            xcom_key: str,
            orm_model: DeclarativeMeta | str,
            condition_field: str,
            *args,
            **kwargs,
    ):
        super().__init__(
            conn_id=conn_id,
            python_callable=self.save,
            *args,
            **kwargs,
        )

        self.xcom_key = xcom_key
        self.orm_model = (
            import_from_string(orm_model) if isinstance(orm_model, str) else orm_model
        )
        self.condition_field = condition_field

    def save(self, session: Session, ti: TaskInstance):
        item_jsons = ti.xcom_pull(key=self.xcom_key)

        if not item_jsons:
            return

        mapper = inspect(self.orm_model)
        column_keys = [col.key for col in mapper.attrs]  # type: ignore

        for item_json in item_jsons:
            item = json.loads(item_json)
            condition_value = item.pop(self.condition_field)

            values = {
                key: item[key]
                for key in column_keys
                if key != self.condition_field and key in item
            }

            for upd_key in ("updated", "updated_at"):
                if upd_key in column_keys:
                    values[upd_key] = datetime.now()

            print(values)

            stmt = (
                update(self.orm_model)
                .where(getattr(self.orm_model, self.condition_field) == condition_value)
                .values(**values)
            )
            session.execute(stmt)


class DeleteOrmOperator(SQLAlchemySessionOperator):

    def __init__(
            self,
            conn_id: str,
            xcom_key: str,
            orm_model: DeclarativeMeta | str,
            *args,
            **kwargs,
    ):
        super().__init__(
            conn_id=conn_id,
            python_callable=self.save,
            *args,
            **kwargs,
        )

        self.xcom_key = xcom_key
        self.orm_model = (
            import_from_string(orm_model) if isinstance(orm_model, str) else orm_model
        )

    def save(self, session: Session, ti: TaskInstance):
        item_jsons = ti.xcom_pull(key=self.xcom_key)

        if not item_jsons:
            return

        mapper = inspect(self.orm_model)
        pk_columns = mapper.primary_key  # type: ignore

        if not pk_columns:
            raise ValueError("Модель не имеет первичного ключа")

        for item_json in item_jsons:
            item_data = json.loads(item_json)

            conditions = [col == item_data[col.key] for col in pk_columns]
            stmt = delete(self.orm_model).where(and_(*conditions))
            session.execute(stmt)
