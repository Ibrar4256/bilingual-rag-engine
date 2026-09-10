FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bilingual_etl/ bilingual_etl/
RUN mkdir -p data

RUN adduser --disabled-password --no-create-home appuser
USER appuser

CMD ["python", "-m", "bilingual_etl.scripts.main_etl"]
