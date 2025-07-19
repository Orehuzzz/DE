from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import pandas as pd
import requests


default_args = {
    'owner':'etl_user',
    'depends_on_past':True,
    'start_date':datetime(2025, 7, 17),
    'retries':1
}

#Можно через airflow.decorators import task ?
def retrieving_csv(**context):
    csv_file = pd.read_csv('./dags/comments.csv', sep=';')
    context['ti'].xcom_push(key='csv_file', value=csv_file)
    return(csv_file)

def retrieving_xlsx(**context):
    xlsx_file = pd.read_excel('./dags/users.xlsx')
    context['ti'].xcom_push(key='xlsx_file', value=xlsx_file)
    return(xlsx_file)

def get_api(**context):
    api_data = requests.get('https://jsonplaceholder.typicode.com/posts')
    df = pd.DataFrame(api_data.json())
    context['ti'].xcom_push(key='api', value=api_data)
    return(df)

with DAG('retrieve_data', default_args=default_args, schedule_interval='@daily', catchup=True, 
          max_active_tasks=3, max_active_runs=1, tags=['dag_retrieves_data', 'first_ex']) as dag:
    
    with TaskGroup('data_preparation') as prep_group:

        csv_task = PythonOperator(
            task_id='give_csv',
            python_callable=retrieving_csv,
        )

        xlsx_task = PythonOperator(
            task_id='give_xlsx',
            python_callable=retrieving_xlsx,
        )

        api_task = PythonOperator(
            task_id='give_api_data',
            python_callable=get_api
        )

    


