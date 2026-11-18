# Sandbox runner: the only service with access to the Docker daemon.
# It is not published on any host port; only the backend can reach it.
FROM python:3.11-slim

WORKDIR /runner
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runner.py .

EXPOSE 8080
CMD ["uvicorn", "runner:app", "--host", "0.0.0.0", "--port", "8080"]
