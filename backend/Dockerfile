FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app/ app/
EXPOSE 8000
ENV MODE=all
ENV PROCESS_TYPE=web
CMD if [ "$PROCESS_TYPE" = "worker" ]; then \
      celery -A app.core.tasks.celery_tasks worker --loglevel=info --concurrency=2; \
    else \
      python -m app.entrypoint; \
    fi
