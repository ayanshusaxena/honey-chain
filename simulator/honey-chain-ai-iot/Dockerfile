FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=5050

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and model artifacts
COPY ai/ ai/
COPY models/ models/
COPY service/ service/
COPY simulator/ simulator/
COPY data/ data/

EXPOSE 5050

HEALTHCHECK --interval=5s --timeout=5s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5050/health')" || exit 1

CMD ["python", "service/ai_service.py"]
