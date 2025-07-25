from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import pandas as pd
import requests



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

    print("Columns in df_xlsx:", df_xlsx.columns.tolist())


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

    