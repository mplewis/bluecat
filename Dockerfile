FROM python:3.10 AS deps

RUN pip install poetry

RUN mkdir -p /app
WORKDIR /app
COPY pyproject.toml poetry.toml poetry.lock ./
RUN poetry install

########################################

FROM python:3.10 AS prod

RUN apt-get update
RUN apt-get install -y bluez bluetooth

RUN mkdir -p /app
WORKDIR /app
COPY . .
COPY --from=deps /app/.venv /app/.venv

EXPOSE 8000
CMD [".venv/bin/uvicorn", "bluecat.main:app", "--host", "0.0.0.0"]
