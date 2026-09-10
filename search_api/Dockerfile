FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY search_api/ search_api/
COPY bilingual_etl/ bilingual_etl/

RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "search_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
