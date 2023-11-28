from typing import List, Dict, Union
from datetime import datetime
import copy
import json
import logging

from airflow.models.taskinstance import TaskInstance
from airflow.hooks.base_hook import BaseHook
from airflow.providers.elasticsearch.hooks.elasticsearch import ElasticsearchPythonHook
from elasticsearch import Elasticsearch, helpers

from settings import (
    DBFields,
    MOVIES_UPDATED_STATE_KEY,
    MOVIES_UPDATED_STATE_KEY_TMP,
    DT_FMT,
)
from db_schemas.es import MOVIES_BASE, MOVIE_FIELDS
from utils import transform


def _es_hosts(conn: BaseHook) -> List[str]:
    """Получение строки подключения Elasticsearch"""
    return [f"http://{conn.host}:{conn.port}"]


def _get_es_connection(connection: str) -> ElasticsearchPythonHook:
    """Получение connection Elasticsearch"""
    conn = BaseHook.get_connection(connection)
    es_hook = ElasticsearchPythonHook(hosts=_es_hosts(conn))
    es_conn = es_hook.get_conn
    return es_conn


def _prepare_query_with_updated_state(ti: TaskInstance) -> Dict:
    """Подготовка updated_state"""
    updated_state = (
            ti.xcom_pull(
                key=MOVIES_UPDATED_STATE_KEY,
            )
            or datetime.min.strftime(DT_FMT)
    )
    logging.info("Movies updated state: %s", updated_state)

    query = {
        "range": {
            "updated_at": {
                "gte": updated_state,
            }
        }
    }
    return query


def _get_transformed_items(init_items: List, fields: List[str]) -> List:
    """Подготовка transformed_items"""
    required_fields = [DBFields[field].value for field in fields]
    logging.info(required_fields)

    transformed_items = []
    for init_item in init_items:
        transformed_item = {}
        for k, v in init_item["_source"].items():
            if k not in required_fields:
                continue
            if k == DBFields.genre.value:
                v = [{"name": vi} for vi in v]
            transformed_item[k] = v
        transformed_items.append(transformed_item)

    return transformed_items


def _get_index_schema(fields: List[str]) -> Dict:
    """Подготовка schema"""
    filed_properties = {
        DBFields[k].value: v for k, v in MOVIE_FIELDS.items() if k in fields
    }
    schema = copy.deepcopy(MOVIES_BASE)
    schema["mappings"]["properties"] = filed_properties
    return schema


def es_get_films_data(ti: TaskInstance, **context) -> str:
    """Сбор обновленных данных"""

    # get es connection
    es_conn = _get_es_connection(context["params"]["in_db_id"])

    query = _prepare_query_with_updated_state(ti)
    logging.info(query)

    items = es_conn.search(
        index=context["params"]["id_db_params"]["index"],
        query=query,
    )

    items = items["hits"]["hits"]
    logging.info(items)

    transformed_items = _get_transformed_items(items, context["params"]["fields"])
    logging.info(transformed_items)

    if transformed_items:
        ti.xcom_push(
            key=MOVIES_UPDATED_STATE_KEY_TMP,
            value=transformed_items[-1]["updated_at"],
        )
    return json.dumps(transformed_items, indent=4)


def es_create_index(ti: TaskInstance, **context):
    """Создание Индекса в Elasticsearch"""
    conn = BaseHook.get_connection(context["params"]["out_db_id"])
    es_hook = ElasticsearchPythonHook(hosts=[f"http://{conn.host}:{conn.port}"])
    es_conn = es_hook.get_conn
    logging.info(context["params"]["fields"])
    logging.info(_get_index_schema(context["params"]["fields"]))
    response = es_conn.indices.create(
        index=context["params"]["out_db_params"]["index"],
        body=_get_index_schema(context["params"]["fields"]),
        ignore=400,
    )
    if "acknowledged" in response:
        if response["acknowledged"]:
            logging.info("Индекс создан: {}".format(response["index"]))
    elif "error" in response:
        logging.error("Ошибка: {}".format(response["error"]["root_cause"]))
    logging.info(response)


def es_preprocess(ti: TaskInstance, **context) -> Union[str, None]:
    """Преобразование данных для Elasticsearch"""
    prev_task = ti.xcom_pull(task_ids="in_db_branch_task")[-1]
    films_data = ti.xcom_pull(task_ids=prev_task)
    if not films_data:
        logging.info("No records need to be updated")
        return

    films_data = json.loads(films_data)
    logging.info(f'{type(films_data)=}')
    logging.info(f'{films_data=}')
    transformed_films_data = []
    for film_data in films_data:
        transformed_film_data = {}
        for fw_column, fw_value in film_data.items():
            if fw_column == DBFields.genre.value:
                fw_value = transform.get_genres(fw_value)
            transformed_film_data[fw_column] = fw_value
        transformed_films_data.append(transformed_film_data)
    return json.dumps(transformed_films_data, indent=4)


def es_write(ti: TaskInstance, **context):
    """Запись данных в Elasticsearch"""
    conn = BaseHook.get_connection(context["params"]["out_db_id"])
    es_hook = ElasticsearchPythonHook(hosts=[f"http://{conn.host}:{conn.port}"])
    es_conn = es_hook.get_conn

    films_data = ti.xcom_pull(task_ids="es_preprocess")
    if not films_data:
        logging.info("No records need to be updated")
        return

    films_data = json.loads(films_data)
    logging.info(films_data)
    logging.info("Processing %x movie:", len(films_data))
    actions = [
        {
            "_index": context["params"]["out_db_params"]["index"],
            "_id": film_data["id"],
            "_source": film_data,
        }
        for film_data in films_data
    ]
    logging.info(actions)
    helpers.bulk(es_conn, actions)
    logging.info("Transfer completed, %x updated", len(actions))
