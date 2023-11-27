from settings import DBFields


MOVIE_FIELDS = {
    DBFields.film_id.name: f"{DBFields.film_id.value} uuid NOT NULL PRIMARY KEY",
    DBFields.rating.name: f"{DBFields.rating.value} FLOAT",
    DBFields.genre.name: f"{DBFields.genre.value} json NOT NULL",
    DBFields.film_type.name: f"{DBFields.film_type.value} TEXT not null",
    DBFields.title.name: f"{DBFields.title.value} TEXT NOT NULL",
    DBFields.description.name: f"{DBFields.description.value} TEXT",
    DBFields.actors.name: f"{DBFields.actors.value} json NOT NULL",
    DBFields.writers.name: f"{DBFields.writers.value} json NOT NULL",
    DBFields.directors.name: f"{DBFields.directors.value} json NOT NULL",
    DBFields.film_created_at.name: f"{DBFields.film_created_at.value} timestamp with time zone",
    DBFields.film_updated_at.name: f"{DBFields.film_updated_at.value} timestamp with time zone",
}
