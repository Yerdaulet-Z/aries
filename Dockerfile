# TODO: Use multi-stage build to reduce final image size (~900MB -> ~200MB).
#       Stage 1: install deps in a builder image. Stage 2: copy only site-packages + app code.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
