# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if needed for PyMuPDF or Postgres)
# libpq-dev is often needed for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements verification
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ ./src/

# Set PYTHONPATH
ENV PYTHONPATH=/app/src

# Default command (can be overridden by Cloud Run Job args)
# Usage: python -m src.main --phase=1 ...
ENTRYPOINT ["python", "-m", "src.main"]
