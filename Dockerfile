# Reproducible env cho BTC dựng lại private test. TODO: chốt base image (CUDA nếu cần GPU).
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mặc định: chạy inference input/ -> output/
CMD ["python", "scripts/run_inference.py"]
