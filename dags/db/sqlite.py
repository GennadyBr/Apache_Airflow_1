from typing import List, Dict, Set, Tuple
from datetime import datetime
import time
import json
import logging
import sqlite3

from contextlib import contextmanager, closing

from airflow.models.taskinstance import TaskInstance
from airflow.hooks.base_hook import BaseHook

from settings import DBFields, SQLiteDBTables, MOVIES_UPDATED_STATE_KEY, MOVIES_UPDATED_STATE_KEY_TMP

SQLITE_FIELDS_TO_SQL = {
    DBFields.film_id.name: "fw.id",
    DBFields.title.name: "fw.title",
    DBFields.description.name: "fw.description",
    DBFields.rating.name: "fw.rating",
    DBFields.film_type.name: "fw.type",
    DBFields.film_created_at.name: "fw.created_at",
    DBFields.film_updated_at.name: "fw.updated_at",
    DBFields.actors.name: "STRING_AGG(DISTINCT p.id::text || ' : ' || p.full_name, ', ') FILTER (WHERE pfw.role = 'actor')",
    DBFields.writers.name: "STRING_AGG(DISTINCT p.id::text || ' : ' || p.full_name, ', ') FILTER (WHERE pfw.role = 'writer')",
    DBFields.directors.name: "STRING_AGG(DISTINCT p.id::text || ' : ' || p.full_name, ', ') FILTER (WHERE pfw.role = 'director')",
    DBFields.genre.name: "STRING_AGG(DISTINCT g.name, ', ')",
}


@contextmanager
def _conn_context(db_name: str) -> sqlite3.Connection:
    """подключение к базе SQLite"""
    if 'out' in db_name:
        db_path = db_name
    else:
        db_path = '/db/' + db_name  # путь до каталога, где лежит скрипт
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # row_factory - данные в формате «ключ-значение»
    yield conn
    conn.close()


def sqlite_get_updated_movies_ids(ti: TaskInstance, **context) -> Set:
    """Сбор обновленных записей в таблице с фильмами"""
    logging.info(f'sqlite_get_updated_movies_ids; context= , {context["params"]}')

    query = f"""
        SELECT id, updated_at
        FROM {SQLiteDBTables.film.value}
        WHERE updated_at >= ?
        ORDER BY updated_at
        LIMIT {context["params"]["chunk_size"]}
        """

    updated_state = ti.xcom_pull(
        key=MOVIES_UPDATED_STATE_KEY, include_prior_dates=True
    ) or str(datetime.min) + '.0'
    logging.info(f'{ti.xcom_pull(key=MOVIES_UPDATED_STATE_KEY, include_prior_dates=True)=}')
    logging.info(f'{str(datetime.min)=}')
    logging.info(f'{updated_state=}, {type(updated_state)=}')
    try:
        updated_state_sqlite = time.mktime(
            datetime.strptime(updated_state[:25], "%Y-%m-%d %H:%M:%S.%f").timetuple())
    except ValueError:
        updated_state_sqlite = updated_state

    msg = f"{updated_state_sqlite=}, {type(updated_state_sqlite)=}"
    logging.info(msg)

    # имя файла базы данных из Admin-Connections-Schema
    db_name = BaseHook.get_connection(context["params"]["in_db_id"]).schema
    logging.info(f"{db_name=}")

    with _conn_context(db_name) as conn:
        with closing(conn.cursor()) as cursor:
            try:
                cursor.execute(query, (updated_state_sqlite,))
                # cursor.execute("""select * from person;""")
                data = cursor.fetchall()
                data_dict = [dict(i) for i in data]
                logging.info(f'{data_dict=}')
            except Exception as err:
                logging.error(f'<<SELECT ERROR>> {err}')

    if data_dict:
        ti.xcom_push(key=MOVIES_UPDATED_STATE_KEY_TMP, value=str(data_dict[-1]["updated_at"]))
    logging.error(f'MOVIES_UPDATED_STATE_KEY_TMP {data_dict[-1]["updated_at"]=}')
    return set([x["id"] for x in data_dict])


def sqlite_get_films_data(ti: TaskInstance, **context):
    """Сбор агрегированных данных по фильмам"""
    logging.info(f'context["params"]["fields"]= {context["params"]["fields"]}')
    fields_query = ", ".join([SQLITE_FIELDS_TO_SQL[field] for field in context["params"]["fields"]])

    film_ids = ti.xcom_pull(task_ids="sqlite_get_updated_movies_ids")
    logging.info(f'film_ids= {film_ids}')
    if len(film_ids) == 0:
        logging.info("No records need to be updated")
        return

    query = f"""
        SELECT {fields_query}
        FROM {SQLiteDBTables.film.value} fw
        LEFT JOIN {SQLiteDBTables.film_person.value} pfw ON pfw.film_work_id = fw.id
        LEFT JOIN {SQLiteDBTables.person.value} p ON p.id = pfw.person_id
        LEFT JOIN {SQLiteDBTables.film_genre.value} gfw ON gfw.film_work_id = fw.id
        LEFT JOIN {SQLiteDBTables.genre.value} g ON g.id = gfw.genre_id
        WHERE fw.id IN {tuple(film_ids)}
        GROUP BY fw.id;
        """
    logging.info(f'query= {query}')

    # имя файла базы данных из Admin-Connections-Schema
    db_name = BaseHook.get_connection(context["params"]["in_db_id"]).schema
    logging.info(f"{db_name=}")

    with _conn_context(db_name) as conn:
        with closing(conn.cursor()) as cursor:
            try:
                cursor.execute(query)
                data = cursor.fetchall()
                data_dict = [dict(i) for i in data]
                logging.info(f'{data_dict[0]=}')
            except Exception as err:
                logging.error(f'<<SELECT ERROR>> {err}')

    return json.dumps(data_dict, indent=4)


def sqlite_preprocess(ti: TaskInstance, **context):
    """Трансформация данных"""
    prev_task = ti.xcom_pull(task_ids="in_db_branch_task")[-1]
    logging.info(f'{prev_task=}')
    films_data = ti.xcom_pull(task_ids=prev_task)
    films_data = json.loads(films_data)
    logging.info(f'{films_data=}')
    if not films_data:
        logging.info("No records need to be updated")
        return

    transformed_films_data = films_data
    logging.info(f'{transformed_films_data=}')

    return json.dumps(transformed_films_data, indent=4)


def _prepare_insert_values_list(films_data: json) -> Tuple[List, Tuple]:
    """Подготовка списка данных к загрузке"""
    values_list = []
    fields = None
    for dict_a in films_data:
        key, value = zip(*dict_a.items())
        fields, values = tuple(key), tuple(value)
        values_list.append(values)
    logging.info(f'{values_list[0]=}')
    return values_list, fields


def _prepare_insert_query(films_data: json, fields: tuple) -> str:
    """Подготовка SQL команды к загрузке"""
    query = f"""
            INSERT OR IGNORE INTO {SQLiteDBTables.film.value} {fields}
            VALUES ({'?' + ',?' * (len(films_data[0]) - 1)});
    """
    logging.info(f'{len(films_data[0])=}')
    logging.info(f'{query}')
    return query


def _prepare_create_query() -> str:
    """Подготовка SQL команды к созданию таблицы"""
    return f"""
            CREATE TABLE IF NOT EXISTS {SQLiteDBTables.film.value} (    
                        id TEXT PRIMARY KEY,
                        title TEXT DEFAULT 'TITLE',
                        description TEXT DEFAULT 'DESCRIPTION',
                        creation_date DATE DEFAULT CURRENT_DATE,
                        file_path TEXT DEFAULT 'FILE_PATH',
                        rating FLOAT DEFAULT 1,
                        type TEXT DEFAULT 'TYPE',
                        created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                        updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
                    );
    """


def drop_table_if_exists(cursor):
    """Удаление таблицы если существует"""
    try:
        cursor.execute("""DROP TABLE IF EXISTS film_work;""")
        logging.info('SUCCESS DROP TABLE')
    except Exception as err:
        logging.error(f'<<DROP TABLE ERROR>> {err}')
        raise err


def create_table(creation_query, cursor):
    """Создание таблицы"""
    try:
        cursor.execute(creation_query)
        logging.info('SUCCESS CREATE TABLE')
    except Exception as err:
        logging.error(f'<<CREATION TABLE ERROR>> {err}')
        raise err


def insert_into_new_table(insertion_query, values_list, cursor):
    """Загрузка данных в таблицу"""
    try:
        cursor.executemany(insertion_query, values_list)
        logging.info(f'INSERTED {cursor.rowcount} records to the table {SQLiteDBTables.film.value}')
        logging.info('SUCCESS INSERT')
    except Exception as err:
        logging.error(f'<<INSERT ERROR>> {err}')
        raise err


def _test_select_count(cursor):
    """Проверка добавления данных в таблицу film_work"""
    try:
        cursor.execute("""SELECT COUNT(*) FROM film_work""")
        data = cursor.fetchall()
        data_dict = [dict(i) for i in data]
        logging.info(f'{len(data_dict)=}')
    except Exception as err:
        logging.error(f'<<SELECT ERROR>> {err}')
        raise err


def sqlite_write(ti: TaskInstance, **context):
    """Запись данных"""
    films_data = ti.xcom_pull(task_ids="sqlite_preprocess")
    logging.info(f'JSON {films_data=}')
    if not films_data:
        logging.info("No records need to be updated")
        return
    films_data = json.loads(films_data)
    logging.info(f'{type(films_data)=}, {films_data=}')

    # имя файла базы данных из Admin-Connections-Schema
    db_name = BaseHook.get_connection(context["params"]["out_db_id"]).schema
    logging.info(f"{db_name=}")

    creation_query = _prepare_create_query()
    values_list, fields = _prepare_insert_values_list(films_data)
    insertion_query = _prepare_insert_query(films_data, fields)

    with _conn_context(db_name) as conn:
        with closing(conn.cursor()) as cursor:
            drop_table_if_exists(cursor)
            conn.commit()

            create_table(creation_query, cursor)
            conn.commit()

            insert_into_new_table(insertion_query, values_list, cursor)
            conn.commit()

            _test_select_count(cursor)
