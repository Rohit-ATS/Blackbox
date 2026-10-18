FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends bash curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x start.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "blackbox.api:app", "--host", "0.0.0.0", "--port", "8000"]
