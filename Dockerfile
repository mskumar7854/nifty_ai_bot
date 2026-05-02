# Use Python 3.11 for newest features and optimizations
FROM python:3.11-slim

# Set timezone to IST (Mumbai)
ENV TZ=Asia/Kolkata
RUN apt-get update && apt-get install -y tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Prevent Python from writing pyc files to disk and ensure logs flow in real-time
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system build dependencies for TA-Lib or heavy numerical libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create the log and data directories for volume mounting
RUN mkdir -p /app/data /app/logs

# Definition of persistent volume mount points
VOLUME ["/app/data", "/app/logs"]

# CMD with -u to guarantee log flushing on VPS
CMD ["python", "-u", "main.py"]
