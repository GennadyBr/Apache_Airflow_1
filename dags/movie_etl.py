from datetime import datetime, timedelta
import logging

from airflow import DAG
from airflow.decorators import dag, task
from airflow.operators.dummy import DummyOperator
from airflow.models.taskinstance import TaskInstance
from airflow.hooks.base_hook import BaseHook
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models.param import Param

from settings import DBFields, MOVIES_UPDATED_STATE_KEY, MOVIES_UPDATED_STATE_KEY_TMP
from db.sqlite import sqlite_get_films_data, sqlite_get_updated_movies_ids, sqlite_preprocess, sqlite_write
from db.pg import (
    pg_get_films_data,
    pg_get_updated_movies_ids,
    pg_create_schema,
    pg_preprocess,
    pg_write,
)
from db.es import es_get_films_data, es_create_index, es_preprocess, es_write

DEFAULT_ARGS = {"owner": "airflow"}


def _check_conn(conn, context_db_params):
    """Проверка Airflow Admin Connection"""
    logging.info(f'{context_db_params=}')
    logging.info(f'{type(context_db_params)=}')
    if conn.conn_type == "postgres":
        if context_db_params["schema"] is None:
            raise AirflowException(
                "You must specify 'schema' for Postgres"
            )
        if context_db_params["table"] is None:
            raise AirflowException(
                "You must specify 'table' for Postgres"
            )
    elif conn.conn_type == "elasticsearch":
        if context_db_params["index"] is None:
            raise AirflowException(
                "You must specify 'index' for ElasticSearch"
            )
    elif conn.conn_type == "sqlite":
        # в sqlite нет схемы и нет индексов
        return
    else:
        raise AirflowException("Unknown input db connection type %s", conn.conn_type)


@task.branch(task_id="in_db_branch_task", trigger_rule="one_success")
def in_db_branch_func(**context):
    """Выбор базы-источника данных"""
    # https://www.restack.io/docs/airflow-faq-authoring-and-scheduling-connections-05
    conn = BaseHook.get_connection(context["params"]["in_db_id"])
    logging.info(conn)
    if conn.conn_type == "postgres":
        return ["pg_get_updated_movies_ids", "pg_get_films_data"]
    elif conn.conn_type == "elasticsearch":
        return ["es_get_films_data"]
    elif conn.conn_type == "sqlite":
        return ["sqlite_get_updated_movies_ids", "sqlite_get_films_data"]
    else:
        raise AirflowException("Unknown input db connection type %s", conn.conn_type)


@task.branch(task_id="out_db_branch_task", trigger_rule="one_success")
def out_db_branch_func(**context):
    """Выбор базы-назначения данных"""
    # https://www.restack.io/docs/airflow-faq-authoring-and-scheduling-connections-05
    conn = BaseHook.get_connection(context["params"]["out_db_id"])
    if conn.conn_type == "postgres":
        return ["pg_preprocess", "pg_create_schema", "pg_write"]
    elif conn.conn_type == "elasticsearch":
        return ["es_preprocess", "es_create_index", "es_write"]
    elif conn.conn_type == "sqlite":
        return ["sqlite_preprocess", "sqlite_write"]
    else:
        raise AirflowException("Unknown input db connection type %s", conn.conn_type)


def in_param_validator(ti: TaskInstance, **context):
    """Проверка указанной базы (источника/назначения) в списке баз"""
    conn = BaseHook.get_connection(context["params"]["in_db_id"])
    logging.info(f'{context["params"]=}')
    _check_conn(conn, context["params"]["id_db_params"])

    conn = BaseHook.get_connection(context["params"]["out_db_id"])
    _check_conn(conn, context["params"]["out_db_params"])


def state_update(ti: TaskInstance, **context):
    """Обновление маркера MOVIES_UPDATED_STATE_KEY"""
    # state = ti.xcom_pull(key=MOVIES_UPDATED_STATE_KEY_TMP)
    state = ti.xcom_pull(key=MOVIES_UPDATED_STATE_KEY)
    logging.info(state)
    if state:
        ti.xcom_push(key=MOVIES_UPDATED_STATE_KEY, value=state)


with DAG(
        "_AIRFLOW_1",
        start_date=days_ago(1),
        schedule_interval=timedelta(minutes=1),
        # schedule_interval="@once",
        default_args=DEFAULT_ARGS,
        tags=["AIRFLOW_1"],
        catchup=False,
        params={
            "chunk_size": Param(11, type="integer", minimum=10),
            "in_db_id": Param(
                "movies_pg_db", type="string", enum=["movies_pg_db", "movies_es_db", "movies_sqlite_db_in"]
            ),
            "id_db_params": Param({"schema": "content", "table": "film_work"}, type=["object", "null"]),
            "fields": Param(["film_id", "title"], type="array", examples=DBFields.keys()),
            "out_db_id": Param(
                "movies_es_db",
                type=["string", "null"],
                enum=[
                    "movies_es_db",
                    "movies_pg_db",
                    "movies_sqlite_db_out"
                ],
            ),
            "out_db_params": Param({"index": "content"}, type=["object", "null"]),
        },
) as dag:
    init = DummyOperator(task_id="init")

    task_validate_params = PythonOperator(
        task_id="in_param_validator",
        python_callable=in_param_validator,
        provide_context=True,
    )

    # https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#branching
    in_branch_op = in_db_branch_func()

    out_branch_op = out_db_branch_func()

    task_update_state = PythonOperator(
        task_id="state_update",
        python_callable=state_update,
        provide_context=True,
        trigger_rule="one_success",
    )

    final = DummyOperator(task_id="final")

    ##### SQLite

    task_sqlite_get_movies_ids = PythonOperator(
        task_id="sqlite_get_updated_movies_ids",
        python_callable=sqlite_get_updated_movies_ids,
        do_xcom_push=True,
        provide_context=True,
    )

    task_sqlite_get_films_data = PythonOperator(
        task_id="sqlite_get_films_data",
        python_callable=sqlite_get_films_data,
        provide_context=True,
    )

    task_sqlite_preprocess = PythonOperator(
        task_id="sqlite_preprocess",
        python_callable=sqlite_preprocess,
        provide_context=True,
    )

    task_sqlite_write = PythonOperator(
        task_id="sqlite_write",
        python_callable=sqlite_write,
        provide_context=True,
    )

    ##### Postgres

    task_pg_get_movies_ids = PythonOperator(
        task_id="pg_get_updated_movies_ids",
        python_callable=pg_get_updated_movies_ids,
        do_xcom_push=True,
        provide_context=True,
    )

    task_pg_get_films_data = PythonOperator(
        task_id="pg_get_films_data",
        python_callable=pg_get_films_data,
        provide_context=True,
    )

    task_pg_create_schema = PythonOperator(
        task_id="pg_create_schema",
        python_callable=pg_create_schema,
        provide_context=True,
    )

    task_pg_preprocess = PythonOperator(
        task_id="pg_preprocess",
        python_callable=pg_preprocess,
        provide_context=True,
    )

    task_pg_write = PythonOperator(
        task_id="pg_write",
        python_callable=pg_write,
        provide_context=True,
    )

    ##### Elasticsearch

    task_es_get_films_data = PythonOperator(
        task_id="es_get_films_data",
        python_callable=es_get_films_data,
        do_xcom_push=True,
        provide_context=True,
    )

    task_es_preprocess = PythonOperator(
        task_id="es_preprocess",
        python_callable=es_preprocess,
        provide_context=True,
    )

    task_es_create_index = PythonOperator(
        task_id="es_create_index",
        python_callable=es_create_index,
        provide_context=True,
    )

    task_es_write = PythonOperator(
        task_id="es_write",
        python_callable=es_write,
        provide_context=True,
    )

init >> task_validate_params >> in_branch_op

in_branch_op >> task_pg_get_movies_ids >> task_pg_get_films_data
task_pg_get_films_data >> out_branch_op

in_branch_op >> task_es_get_films_data
task_es_get_films_data >> out_branch_op

in_branch_op >> task_sqlite_get_movies_ids >> task_sqlite_get_films_data >> out_branch_op

out_branch_op >> task_pg_preprocess >> task_pg_create_schema >> task_pg_write
task_pg_write >> task_update_state

out_branch_op >> task_es_preprocess >> task_es_create_index >> task_es_write
task_es_write >> task_update_state

out_branch_op >> task_sqlite_preprocess >> task_sqlite_write >> task_update_state

task_update_state >> final
