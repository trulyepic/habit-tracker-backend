.PHONY: dev prod-db shell migrate

dev:
	@unset DATABASE_URL; \
	source env/bin/activate; \
	python manage.py runserver

prod-db:
	@source env/bin/activate; \
	export DATABASE_URL="$$(grep -E '^DATABASE_URL=' .env.local | sed 's/DATABASE_URL=//')"; \
	if [ -z "$$DATABASE_URL" ]; then echo "DATABASE_URL is not set in .env.local"; exit 1; fi; \
	python manage.py runserver

shell:
	@source env/bin/activate; python manage.py shell

migrate:
	@source env/bin/activate; python manage.py migrate