FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-lato libglib2.0-0 libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
COPY themes ./themes
RUN useradd --create-home --uid 10001 renderer
USER renderer
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
