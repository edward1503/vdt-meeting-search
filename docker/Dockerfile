# Optional: Full container deploy (CPU-only, no GPU)
# For GPU inference, run API directly on host instead.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/e5-base-v2')"

COPY src/ src/
COPY frontend/ frontend/

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
