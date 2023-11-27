from settings import DBFields


MOVIES_BASE = {
    "settings": {
        "refresh_interval": "1s",
        "analysis": {
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "english_possessive_stemmer": {
                    "type": "stemmer",
                    "language": "possessive_english",
                },
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
            },
            "analyzer": {
                "ru_en": {
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "english_stop",
                        "english_stemmer",
                        "english_possessive_stemmer",
                        "russian_stop",
                        "russian_stemmer",
                    ],
                }
            },
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {},
    },
}


MOVIE_FIELDS = {
    DBFields.film_id.name: {"type": "keyword"},
    DBFields.rating.name: {"type": "float"},
    DBFields.genre.name: {"type": "keyword"},
    DBFields.film_type.name: {"type": "keyword"},
    DBFields.title.name: {
        "type": "text",
        "analyzer": "ru_en",
        "fields": {"raw": {"type": "keyword"}},
    },
    DBFields.description.name: {"type": "text", "analyzer": "ru_en"},
    DBFields.actors.name: {
        "type": "nested",
        "dynamic": "strict",
        "properties": {
            "id": {"type": "keyword"},
            "full_name": {"type": "text", "analyzer": "ru_en"},
        },
    },
    DBFields.writers.name: {
        "type": "nested",
        "dynamic": "strict",
        "properties": {
            "id": {"type": "keyword"},
            "full_name": {"type": "text", "analyzer": "ru_en"},
        },
    },
    DBFields.directors.name: {
        "type": "nested",
        "dynamic": "strict",
        "properties": {
            "id": {"type": "keyword"},
            "full_name": {"type": "text", "analyzer": "ru_en"},
        },
    },
    DBFields.film_created_at.name: {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
    DBFields.film_updated_at.name: {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
}
