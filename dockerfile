FROM nvidia/cuda:12.0.1-base-ubuntu22.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    libexif-dev \
    libexif12 \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy pre-downloaded models
COPY models/ /app/models/

# Copy application code
COPY app/ /app/
COPY config.yml /app/

# Expose API port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]
