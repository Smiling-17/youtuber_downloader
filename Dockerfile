FROM python:3.12-slim

# Cài ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Render sẽ gán biến PORT
ENV PORT 10000
EXPOSE 10000

# Chạy ứng dụng
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
