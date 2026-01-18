FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create directory for config
RUN mkdir -p /app/config

# Expose web port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command - run web server
CMD ["python", "-m", "uvicorn", "qbit_arr.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
