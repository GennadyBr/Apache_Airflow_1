# Презентация кастомного ETL сервиса на Airflow для оркестрации миграции данных 
- из SQLite в Postgresql для внутренних служб корпорации
- из Postgresql в Elasticseach для организации полнотекстового поиска по данным

**проект создан для демонстрации Airflow, в нем реализованы следующие возможности**
- задание параметров через DAG Params
- операторы ветвления Airflow

## Запуск проекта на сайте
http://5.35.83.245:8080/home

### Авторизация
- login **airflow**
- pass **airflow**

### Название DAG
- **_AIRFLOW_1**

### Доступ к Postgresql
- host: **5.35.83.245**
- port: **5432**
- database: **movies_database**
- login **app**
- pass **123qwe**

### Доступ к Elasticsearch
http://5.35.83.245:9200/content/_search?pretty=true


## Запуск проекта локально
### Скачать проект на локальную машину

- git clone

[Ссылка на проект](https://github.com/GennadyBr/airflow_1)

### Запустить проект на локальной машине
- docker compose up -d --build

### Настройка Airflow-Admin-Connection
### Postgres
- Connection Id **movies_pg_db**
- Connection Type **Postgres**
- Host 	**movies_pg_db**
- Schema 	**movies_database**
- Login 	**app**
- Password **123qwe**
- Port 	**5432**
- Extra 	**{"cursor": "RealDictCursor"}**

### Elasticsearch
- Connection **Id movies_es_db**
- Connection Type **Elasticseach**
- Host 	**movies_es_db**
- Port 	**9200**

### SQLite - база источник данных
- Connection Id **movies_sqlite_db_in**
- Connection Type **SQLite**
- Schema 	**db_in.sqlite**

### SQLite - база получатель данных
- Connection Id **movies_sqlite_db_out**
- Connection Type **SQLite**
- Schema 	**db_out.sqlite**



### Настойка DAG Params
### Postgres
- in_db_id: 	**movies_pg_db**
- id_db_params: 	**{"schema": "content"}**
- out_db_id: 	**movies_pg_db**
- out_db_params: 	**{"schema": "content", "table": "film_work"}**


### Elasticsearch
- in_db_id: 	**movies_es_db**
- in_out_id: 	**movies_es_db**
- id_db_params и out_db_params: 	**{"index": "content"}**

### SQLite
- id_db_params и out_db_params: можно не заполнять

### fields
- **film_id, title** (выбрать из списка доступные поля)

### Количество строк для переноса за 1 раз
- chunk_size *: **10**











