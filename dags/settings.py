from enum import Enum


MOVIES_UPDATED_STATE_KEY = "movies_state"
MOVIES_UPDATED_STATE_KEY_TMP = "movies_state_tmp"
DT_FMT = "%Y-%m-%d %H:%M:%S"
DT_FMT_PG = "YYYY-MM-DD HH24:MI:SS"


class ExtendedEnum(Enum):
    @classmethod
    def values(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def keys(cls):
        return list(map(lambda c: c.name, cls))


class DBFields(str, ExtendedEnum):
    film_id = "id"
    title = "title"
    description = "description"
    rating = "rating"
    film_type = "type"
    film_created_at = "created_at"
    film_updated_at = "updated_at"
    actors = "actors"
    writers = "writers"
    directors = "directors"
    genre = "genre"


class PGDBTables(str, ExtendedEnum):
    film = "film_work"
    genre = "genre"
    person = "person"
    film_genre = "genre_film_work"
    film_person = "person_film_work"

    
class SQLiteDBTables(str, ExtendedEnum):
    film = "film_work"
    genre = "genre"
    person = "person"
    film_genre = "genre_film_work"
    film_person = "person_film_work"

    
    