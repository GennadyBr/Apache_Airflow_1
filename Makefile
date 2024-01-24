upv:
	sudo docker-compose up -d --build

downv:
	sudo docker-compose down --remove-orphans

psv:
	sudo docker-compose ps

up:
	docker compose up -d --build

down:
	docker compose down --remove-orphans

ps:
	docker compose ps

venv:
	sudo python3.11 -m venv venv

net:
	sudo docker network create nginx_proxy