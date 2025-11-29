FROM python:3.13-slim-bookworm as base

WORKDIR /app
EXPOSE 8501

COPY pyproject.toml pyproject.toml

RUN pip3 install -e .

COPY ./src /app/src

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
ENTRYPOINT [ "streamlit", "run", "/app/src/main.py", "--server.port=8501", "--server.address=0.0.0.0" ]

FROM base as dev

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install -e.[dev]
