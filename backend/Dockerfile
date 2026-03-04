FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app/ app/
EXPOSE 8000
ENV MODE=all
CMD ["python", "-m", "app.entrypoint"]
