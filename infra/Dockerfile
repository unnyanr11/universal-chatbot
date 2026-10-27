FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY services ./services
RUN pip install --no-cache-dir . && useradd --create-home assistant
USER assistant
EXPOSE 8000
CMD ["uvicorn", "platform_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
