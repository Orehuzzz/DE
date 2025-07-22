# from datetime import datetime
# from airflow import DAG
# from airflow.decorators import task
# from airflow.operators.python import PythonOperator
# from airflow.utils.task_group import TaskGroup
import pandas as pd
import requests


# default_args = {
#     'owner':'etl_user',
#     'depends_on_past':True,
#     'start_date':datetime(2025, 7, 17),
#     'retries':1
# }


def retrieving_csv():
    csv_file = pd.read_csv('./dags/comments.csv', sep=';')

    return(csv_file)

def retrieving_xlsx():
    xlsx_file = pd.read_excel('./dags/users.xlsx')

    return(xlsx_file)

def get_api():
    api_data = requests.get('https://jsonplaceholder.typicode.com/posts')
    df = pd.DataFrame(api_data.json())
    return(df)

def union_data():
    df_csv = pd.DataFrame(retrieving_csv())    
    df_xlsx = pd.DataFrame(retrieving_xlsx())
    df_api = pd.DataFrame(get_api())
#подумать над объединением 
    join_data = pd.merge(df_api, df_csv, how='left', on='userId')
    join_data = join_data.rename(columns={'id_x' : 'id'})
    join_data.to_excel('check_join.xlsx', index=True)

    union_data = pd.merge(join_data, df_xlsx, how='left', on='id')

    print(union_data)

    union_data.to_excel('excel_table.xlsx', index=True)

union_data()


# with DAG('retrieve_data', default_args=default_args, schedule_interval='@daily', catchup=True, 
#           max_active_tasks=3, max_active_runs=1, tags=['dag_retrieves_data', 'first_ex']) as dag:
    
#     with TaskGroup('Extract') as prep_group:

#         @task
#         def retrieving_csv(**context):
#             csv_file = pd.read_csv('./dags/comments.csv', sep=';')
#             context['ti'].xcom_push(key='csv_file', value=csv_file)
#             return(csv_file)

#         @task
#         def retrieving_xlsx(**context):
#             xlsx_file = pd.read_excel('./dags/users.xlsx')
#             context['ti'].xcom_push(key='xlsx_file', value=xlsx_file)
#             return(xlsx_file)
        
#         @task
#         def get_api(**context):
#             api_data = requests.get('https://jsonplaceholder.typicode.com/posts')
#             df = pd.DataFrame(api_data.json())
#             context['ti'].xcom_push(key='api', value=api_data)
#             return(df)
            
#         csv_task = retrieving_csv()
#         xlsx_task = retrieving_xlsx()
#         api_task = get_api()


