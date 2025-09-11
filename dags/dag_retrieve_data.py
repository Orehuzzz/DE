from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.utils.task_group import TaskGroup
from airflow.hooks.base_hook import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, Float, String, DATE
from sqlalchemy.orm import declarative_base
import pandas as pd
import requests
import boto3
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq
import awswrangler as wr
import pg8000



default_args = {
    'owner':'etl_user',
    # 'depends_on_past':True,
    'start_date':datetime(2025, 7, 17),
    'retries':0
}

def take_csv(**context):
    csv_file = pd.read_csv('./dags/comments.csv', sep=';')
    context['ti'].xcom_push(key='csv_file', value=csv_file.to_dict(orient='records'))
    return csv_file

def take_xlsx(**context):
    xlsx_file = pd.read_excel('./dags/users.xlsx')
    context['ti'].xcom_push(key='xlsx_file', value=xlsx_file.to_dict(orient='records'))
    return xlsx_file

def take_api(**context):
    api_data = requests.get('https://jsonplaceholder.typicode.com/posts')
    df = pd.DataFrame(api_data.json())
    context['ti'].xcom_push(key='api_file', value=df.to_dict(orient='records'))
    return df

def union_data(**context):
    ti = context['ti']
    
    df_csv = pd.DataFrame(ti.xcom_pull(task_ids='data_preparation.take_csv', key='csv_file'))
    df_xlsx = pd.DataFrame(ti.xcom_pull(task_ids='data_preparation.take_xlsx', key='xlsx_file'))
    df_api = pd.DataFrame(ti.xcom_pull(task_ids='data_preparation.take_api_data', key='api_file'))

    df_xlsx.rename(columns={'id':'userId'}, inplace=True)
    df_xlsx['name'] = df_xlsx['name'].str.replace('Mrs. ', '', regex=False)

    join_data = pd.merge(df_csv, df_api, how='left', on='id')
    join_data = join_data.rename(columns={'id_x': 'id'})
    join_data.pop('title_y')
    join_data.pop('userId_y')
    join_data.pop('title_x')
    join_data.rename(columns={'userId_x':'userId'}, inplace=True)
    join_data.to_excel('check_join.xlsx', index=True)

    import ast
    union_data = pd.merge(df_xlsx, join_data, how='left', on='userId')

    union_data[['name', 'surname']] = union_data['name'].str.split(' ', n=1, expand=True)

    cols = list(union_data.columns)
    cols.remove('surname')
    cols.insert(2, 'surname')
    union_data = union_data[cols]

    union_data['address'] = union_data['address'].apply(ast.literal_eval)
    union_data['address'] = union_data['address'].apply(lambda x: f"{x['city']}, {x['street']}, {x['suite']}" if isinstance(x, dict) else None)
    union_data.rename(columns={'address':'company_address'}, inplace=True)
    union_data['company'] = union_data['company'].apply(ast.literal_eval)
    union_data['company'] = union_data['company'].apply(lambda x: f"{x['name']}" if isinstance(x, dict) else None)
    union_data.rename(columns={'company':'company_name'}, inplace=True)
    union_data.rename(columns={'body':'content_of_comment'}, inplace=True)
    union_data.pop('userId')

    union_data.to_excel('excel_table.xlsx', index=False)

    ti.xcom_push(key='union_data', value=union_data.to_dict())

    return union_data
    
def push_to_minio(**context):
    ti = context['ti']
    df_dict = ti.xcom_pull(task_ids='data_preparation.union_all_data', key='union_data')
    df = pd.DataFrame(df_dict)

    table = pa.Table.from_pandas(df)
    buffer = BytesIO()
    pq.write_table(table, buffer)
    buffer.seek(0)

    conn = BaseHook.get_connection("minio_aws")
    minio_client = boto3.client(
        's3',
        endpoint_url=conn.extra_dejson.get('endpoint_url'),  
        aws_access_key_id=conn.login,
        aws_secret_access_key=conn.password,
        region_name=conn.extra_dejson.get('region_name') 
    )

    #создаём уникальное имя файла 
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bucket_name = Variable.get('bucket_name')
    object_key = f'union_data/final_data_{timestamp}.parquet'

    existing_buckets = [b['Name'] for b in minio_client.list_buckets()['Buckets']]
    if bucket_name not in existing_buckets:
        minio_client.create_bucket(Bucket=bucket_name)


    minio_client.upload_fileobj(buffer, bucket_name, object_key)
    print(f"File uploaded to MinIO: s3://{bucket_name}/{object_key}") #проверяем местоположение


def create_table(**context):

    conn_data = BaseHook.get_connection("postgres")

    conn = pg8000.connect(
        user=conn_data.login,
        password=conn_data.password,
        host=conn_data.host,
        port=int(conn_data.port),
        database="airflow"
    )

    create_sql = """
    CREATE TABLE IF NOT EXISTS airflow_data.user_data (
        dwh_id SERIAL PRIMARY KEY,
        id INTEGER NOT NULL UNIQUE,
        name VARCHAR(255),
        surname VARCHAR(255),
        username VARCHAR(100),
        email VARCHAR(255),
        company_address TEXT,
        phone VARCHAR(50),
        website VARCHAR(255),
        company_name VARCHAR(255),
        content_of_comment TEXT
    );
    """

    try:
        cursor = conn.cursor()
        cursor.execute(create_sql)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_data_from_minio(**context):

    conn=BaseHook.get_connection('minio_aws')

    minio_client = boto3.client(
        's3',
        endpoint_url=conn.extra_dejson.get('endpoint_url'),
        aws_access_key_id=conn.login,
        aws_secret_access_key=conn.password,
        region_name=conn.extra_dejson.get('region_name')
    )

    bucket_name = Variable.get('bucket_name')
    object_key = 'union_data/final_data.parquet'
    
    buffer = BytesIO()
    minio_client.download_fileobj(bucket_name, object_key, buffer)
    buffer.seek(0)

    df = pd.read_parquet(buffer)
    df = df.drop_duplicates(subset=['id'])
    
    context['ti'].xcom_push(key='minio_data', value=df.to_dict(orient='records'))

def insert_data_to_postgres(**context):
    ti = context['ti']
    df_dict = ti.xcom_pull(task_ids='load_data_from_minio', key = 'minio_data')
    df = pd.DataFrame(df_dict)

    conn_data = BaseHook.get_connection('postgres')

    conn = pg8000.connect(
        user=conn_data.login,
        password=conn_data.password,
        host=conn_data.host,
        port=int(conn_data.port),
        database='airflow'
    )

    try:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            insert_sql = """
            INSERT INTO airflow_data.user_data 
            (id, name, surname, username, email, company_address, phone, website, company_name, content_of_comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """
            
            cursor.execute(insert_sql, (
                int(row['id']),
                str(row['name']),
                str(row['surname']),
                str(row['username']),
                str(row['email']),
                str(row['company_address']),
                str(row['phone']),
                str(row['website']),
                str(row['company_name']),
                str(row['content_of_comment'])
            ))
        
        conn.commit()
        print(f"Успешно вставлено {len(df)} записей")
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при вставке данных: {str(e)}")
        raise
    finally:
        conn.close()

def log_union_data():
    hook = PostgresHook(postgres_conn_id="postgres")
    conn = hook.get_conn()

    df = pd.read_sql('SELECT * FROM airflow_data.user_data', conn)

    print(df.head(5).to_string(index=False))


with DAG('retrieve_data', default_args=default_args, schedule_interval='@daily', catchup=False, 
           tags=['dag_retrieves_data', 'first_ex']) as dag:
    
    with TaskGroup('data_preparation') as prep_group:

        csv_task = PythonOperator(
            task_id='take_csv',
            python_callable=take_csv,
        )

        xlsx_task = PythonOperator(
            task_id='take_xlsx',
            python_callable=take_xlsx,
        )

        api_task = PythonOperator(
            task_id='take_api_data',
            python_callable=take_api
        )

        union_task = PythonOperator(
            task_id='union_all_data',
            python_callable=union_data
        )

        [csv_task, xlsx_task, api_task] >> union_task

push_task = PythonOperator(
    task_id='push_to_minio',
    python_callable=push_to_minio
)

create_table_task = PythonOperator(
    task_id = 'create_data_table',
    python_callable=create_table,
)


load_data_from_min = PythonOperator(
    task_id='load_data_from_minio',
    python_callable=load_data_from_minio
)

insert_data_task = PythonOperator(
    task_id='insert_data_to_postgres',
    python_callable=insert_data_to_postgres,
)

new_phone = Variable.get('new_phone_number')

update_phone_task = PostgresOperator(
    task_id='update_ph_num',
    postgres_conn_id='postgres',
    sql=f"""
        UPDATE airflow_data.user_data
        SET phone = '{new_phone}'
        WHERE email = 'Shanna@melissa.tv'
    """
)

log_data = PythonOperator(
    task_id='log_union_data',
    python_callable=log_union_data
)

union_task >> push_task >> create_table_task >> load_data_from_min >> insert_data_task >> update_phone_task >> log_data

       