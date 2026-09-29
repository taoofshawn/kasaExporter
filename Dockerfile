FROM python:3.12.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    python-kasa==0.10.2 \
    prometheus-client==0.26.0

COPY kasa_exporter.py /app/kasa_exporter.py

EXPOSE 9498
CMD ["python", "/app/kasa_exporter.py"]
