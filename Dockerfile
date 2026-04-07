# Base Python image
FROM python:3.12-slim

# Configure Python environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    supervisor \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create log files and assign permissions for HuggingFace Spaces
RUN touch /etc/nginx/blocklist.conf && \
    chmod 777 /etc/nginx/blocklist.conf && \
    touch /var/log/auth.log && \
    chmod 777 /var/log/auth.log && \
    chmod -R 777 /var/log/nginx && \
    chmod -R 777 /var/www/html && \
    mkdir -p /var/log/supervisor && \
    chmod -R 777 /var/log/supervisor && \
    mkdir -p /var/run && \
    chmod -R 777 /var/run && \
    mkdir -p /var/lib/nginx && \
    chmod -R 777 /var/lib/nginx

# Copy config files
COPY nginx-default /etc/nginx/sites-available/default
COPY requirements.txt .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy app code
COPY . .

# Fix Windows line endings and make scripts executable
RUN dos2unix /app/scripts/*.sh && \
    chmod +x /app/scripts/*.sh

# Install Python dependencies
RUN pip install --no-cache-dir .

# Make the attack scripts executable
RUN chmod +x scripts/*.sh

# Expose port for HF
EXPOSE 7860

# Start Supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
