# SpatialScan API gateway.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY spatialscan_api ./spatialscan_api
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "spatialscan_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
