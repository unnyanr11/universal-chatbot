FROM node:24-slim AS frontend
WORKDIR /build
COPY apps/admin/package*.json apps/admin/
RUN cd apps/admin && npm ci
COPY apps/admin apps/admin
COPY packages packages
RUN cd apps/admin && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY services ./services
COPY --from=frontend /build/services/api/platform_api/web services/api/platform_api/web
RUN pip install --no-cache-dir . && useradd --create-home assistant
USER assistant
EXPOSE 8000
CMD ["uvicorn", "platform_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
