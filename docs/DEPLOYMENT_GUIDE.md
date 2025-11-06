# Deployment Guide

Complete guide for deploying the Binance Trading Bot in various environments.

## Table of Contents
1. [Deployment Options](#deployment-options)
2. [Local Development Setup](#local-development-setup)
3. [Production Deployment](#production-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Database Setup](#database-setup)
8. [Security Best Practices](#security-best-practices)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Backup and Recovery](#backup-and-recovery)
11. [Troubleshooting](#troubleshooting)

---

## Deployment Options

### 1. Local Development (Docker Compose)
**Best for**: Testing, development, backtesting
**Requirements**: Docker, Docker Compose
**Complexity**: ⭐ Easy

### 2. Production Server (Docker + Nginx)
**Best for**: Small-scale production, VPS deployment
**Requirements**: Linux server, Docker, Nginx
**Complexity**: ⭐⭐ Moderate

### 3. Cloud Deployment (AWS/GCP/Azure)
**Best for**: Large-scale production, high availability
**Requirements**: Cloud provider account, Kubernetes knowledge
**Complexity**: ⭐⭐⭐ Advanced

---

## Local Development Setup

### Prerequisites

**Required**:
- Docker Desktop 20.10+ ([Download](https://www.docker.com/products/docker-desktop))
- Docker Compose 2.0+
- Git
- 4GB RAM minimum, 8GB recommended
- 10GB free disk space

**Optional**:
- Make (Linux/Mac) or use `run.bat` (Windows)
- Python 3.11+ (for running scripts outside Docker)
- Node.js 18+ (for frontend development)

### Quick Start

#### Linux/Mac

```bash
# Clone repository
git clone https://github.com/your-username/binance-bot.git
cd binance-bot

# Start services
docker-compose up -d

# Run initial setup
make setup

# Download historical data
make download-long

# Access the application
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# Django Admin: http://localhost:8000/admin
```

#### Windows

```cmd
# Clone repository
git clone https://github.com/your-username/binance-bot.git
cd binance-bot

# Start services
docker-compose up -d

# Run initial setup
run.bat setup

# Download historical data
run.bat download-long

# Access the application
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# Django Admin: http://localhost:8000/admin
```

### Verify Installation

```bash
# Check all containers are running
docker-compose ps

# Expected output:
# NAME                    STATUS              PORTS
# binancebot_backend      Up                  0.0.0.0:8000->8000/tcp
# binancebot_frontend     Up                  0.0.0.0:5173->5173/tcp
# binancebot_postgres     Up                  5432/tcp
# binancebot_redis        Up                  6379/tcp
# binancebot_celery       Up                  -
# binancebot_celery_beat  Up                  -

# Test backend API
curl http://localhost:8000/api/signals/

# Test frontend
curl http://localhost:5173
```

---

## Production Deployment

### Server Requirements

**Minimum**:
- **CPU**: 2 cores
- **RAM**: 4GB
- **Disk**: 20GB SSD
- **OS**: Ubuntu 22.04 LTS (recommended)
- **Network**: Static IP, domain name (optional)

**Recommended**:
- **CPU**: 4 cores
- **RAM**: 8GB
- **Disk**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Network**: Static IP, SSL certificate

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Nginx
sudo apt install nginx -y

# Install Certbot (for SSL)
sudo apt install certbot python3-certbot-nginx -y

# Logout and login to apply docker group
exit
```

### Step 2: Clone and Configure

```bash
# Clone repository
git clone https://github.com/your-username/binance-bot.git
cd binance-bot

# Create production environment file
cp .env.example .env.production

# Edit environment variables
nano .env.production
```

**Production .env.production**:
```bash
# Django
DJANGO_SECRET_KEY=your-super-secret-key-change-this
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Database
POSTGRES_DB=binancebot
POSTGRES_USER=binancebot
POSTGRES_PASSWORD=strong-password-change-this
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Binance API (optional for live trading)
BINANCE_API_KEY=your-api-key
BINANCE_API_SECRET=your-api-secret
BINANCE_TESTNET=True  # Set to False for production

# Email (for notifications)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# Sentry (optional monitoring)
SENTRY_DSN=your-sentry-dsn
```

### Step 3: Create Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: binancebot_postgres
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file:
      - .env.production
    networks:
      - binancebot_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: binancebot_redis
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - binancebot_network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: binancebot_backend
    restart: always
    volumes:
      - ./backend:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    env_file:
      - .env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - binancebot_network
    command: >
      sh -c "python manage.py migrate &&
             python manage.py collectstatic --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120"

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: binancebot_celery_worker
    restart: always
    volumes:
      - ./backend:/app
    env_file:
      - .env.production
    depends_on:
      - redis
      - postgres
    networks:
      - binancebot_network
    command: celery -A config worker -l info --concurrency=4

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: binancebot_celery_beat
    restart: always
    volumes:
      - ./backend:/app
    env_file:
      - .env.production
    depends_on:
      - redis
      - postgres
    networks:
      - binancebot_network
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

  frontend:
    build:
      context: ./client
      dockerfile: Dockerfile.prod
      args:
        - VITE_API_URL=https://yourdomain.com/api
    container_name: binancebot_frontend
    restart: always
    networks:
      - binancebot_network

  nginx:
    image: nginx:alpine
    container_name: binancebot_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/prod.conf:/etc/nginx/conf.d/default.conf
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    depends_on:
      - backend
      - frontend
    networks:
      - binancebot_network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  binancebot_network:
    driver: bridge
```

### Step 4: Create Production Nginx Config

Create `nginx/prod.conf`:

```nginx
# Upstream services
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:80;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Django admin
    location /admin/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (future)
    location /ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
}
```

### Step 5: Create Production Dockerfiles

**backend/Dockerfile.prod**:
```dockerfile
FROM python:3.11-slim

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn

# Copy application
COPY . .

# Create staticfiles directory
RUN mkdir -p /app/staticfiles

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1
```

**client/Dockerfile.prod**:
```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build application
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**client/nginx.conf**:
```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;
}
```

### Step 6: Deploy

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Create superuser
docker exec -it binancebot_backend python manage.py createsuperuser

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Reload Nginx
docker exec binancebot_nginx nginx -s reload
```

### Step 7: Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Verify
sudo ufw status
```

---

## Docker Deployment

### Production Docker Compose Overview

**Services**:
1. **postgres**: PostgreSQL database
2. **redis**: Redis cache and message broker
3. **backend**: Django application (Gunicorn)
4. **celery_worker**: Async task processor
5. **celery_beat**: Task scheduler
6. **frontend**: React application (Nginx)
7. **nginx**: Reverse proxy and SSL termination

### Environment Variables

Create separate `.env` files for each environment:

**.env.development**:
```bash
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=dev-secret-key
```

**.env.production**:
```bash
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=production-secret-key-change-this
```

**.env.local** (not committed):
```bash
BINANCE_API_KEY=your-real-api-key
BINANCE_API_SECRET=your-real-api-secret
```

### Docker Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery_worker

# Restart specific service
docker-compose restart backend

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild specific service
docker-compose up -d --build backend

# Execute command in container
docker exec -it binancebot_backend python manage.py shell

# View resource usage
docker stats
```

---

## Cloud Deployment

### AWS Deployment (ECS + RDS)

#### Architecture
```
Route 53 → CloudFront → ALB → ECS Fargate
                              ↓
                         RDS PostgreSQL
                         ElastiCache Redis
```

#### Requirements
- AWS Account
- AWS CLI configured
- Terraform or AWS CDK (optional)

#### Step 1: Create RDS Instance

```bash
# Create PostgreSQL RDS instance
aws rds create-db-instance \
    --db-instance-identifier binancebot-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.3 \
    --master-username admin \
    --master-user-password YourPassword123! \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxx \
    --db-subnet-group-name default \
    --backup-retention-period 7 \
    --preferred-backup-window "03:00-04:00" \
    --publicly-accessible false
```

#### Step 2: Create ElastiCache Redis

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
    --cache-cluster-id binancebot-redis \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1 \
    --security-group-ids sg-xxxxx \
    --subnet-group-name default
```

#### Step 3: Push Docker Images to ECR

```bash
# Create ECR repositories
aws ecr create-repository --repository-name binancebot/backend
aws ecr create-repository --repository-name binancebot/frontend

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t binancebot/backend -f backend/Dockerfile.prod backend/
docker tag binancebot/backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/binancebot/backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/binancebot/backend:latest
```

#### Step 4: Create ECS Task Definition

`task-definition.json`:
```json
{
  "family": "binancebot",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/binancebot/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DJANGO_DEBUG", "value": "False"},
        {"name": "POSTGRES_HOST", "value": "binancebot-db.xxxxx.us-east-1.rds.amazonaws.com"}
      ],
      "secrets": [
        {
          "name": "DJANGO_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxxxx:secret:django-secret"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/binancebot",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "backend"
        }
      }
    }
  ]
}
```

#### Step 5: Create ECS Service

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name binancebot

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
    --cluster binancebot \
    --service-name binancebot-backend \
    --task-definition binancebot \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:xxxxx:targetgroup/binancebot/xxxxx,containerName=backend,containerPort=8000"
```

### Google Cloud Platform (GKE)

#### Kubernetes Deployment

**deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: binancebot-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: binancebot-backend
  template:
    metadata:
      labels:
        app: binancebot-backend
    spec:
      containers:
      - name: backend
        image: gcr.io/your-project/binancebot-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DJANGO_DEBUG
          value: "False"
        - name: POSTGRES_HOST
          valueFrom:
            secretKeyRef:
              name: binancebot-secrets
              key: postgres-host
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## Environment Configuration

### Configuration Files

**1. Django Settings** (`backend/config/settings.py`):
```python
# Use environment-specific settings
ENVIRONMENT = os.getenv('DJANGO_ENV', 'development')

if ENVIRONMENT == 'production':
    from .settings_prod import *
elif ENVIRONMENT == 'staging':
    from .settings_staging import *
else:
    from .settings_dev import *
```

**2. Frontend Environment** (`.env.production`):
```bash
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com/ws
VITE_ENV=production
VITE_ENABLE_ANALYTICS=true
```

---

## Database Setup

### Initial Migration

```bash
# Run migrations
docker exec binancebot_backend python manage.py migrate

# Create superuser
docker exec -it binancebot_backend python manage.py createsuperuser

# Load initial data (optional)
docker exec binancebot_backend python manage.py loaddata initial_data.json
```

### Database Backup

```bash
# Backup
docker exec binancebot_postgres pg_dump -U binancebot binancebot > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20241106.sql | docker exec -i binancebot_postgres psql -U binancebot binancebot
```

### Automated Backups (Cron)

```bash
# Add to crontab
crontab -e

# Daily backup at 3 AM
0 3 * * * docker exec binancebot_postgres pg_dump -U binancebot binancebot | gzip > /backups/binancebot_$(date +\%Y\%m\%d).sql.gz

# Keep only last 30 days
0 4 * * * find /backups -name "binancebot_*.sql.gz" -mtime +30 -delete
```

---

## Security Best Practices

### 1. Environment Variables
- Never commit `.env` files
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Rotate secrets regularly

### 2. Django Security
```python
# settings.py
DEBUG = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### 3. Database Security
- Use strong passwords
- Enable SSL connections
- Restrict network access
- Regular backups

### 4. API Key Security
- Store in environment variables
- Never log API keys
- Use IP whitelist on Binance
- Enable API key restrictions

---

## Monitoring and Logging

### Application Monitoring (Sentry)

```bash
# Install Sentry
pip install sentry-sdk

# Configure in settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    environment=os.getenv('DJANGO_ENV', 'development')
)
```

### Logging Configuration

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/binancebot/django.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Docker Logs

```bash
# View logs
docker-compose logs -f --tail=100 backend

# Export logs
docker-compose logs > logs_$(date +%Y%m%d).txt

# Configure log rotation
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

## Backup and Recovery

### Backup Strategy

**Daily Backups**:
- Database (pg_dump)
- User uploads (media files)
- Configuration files

**Weekly Backups**:
- Full server snapshot
- Docker volumes

**Backup Script** (`backup.sh`):
```bash
#!/bin/bash

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
docker exec binancebot_postgres pg_dump -U binancebot binancebot | gzip > "${BACKUP_DIR}/db_${DATE}.sql.gz"

# Media files backup
tar -czf "${BACKUP_DIR}/media_${DATE}.tar.gz" -C backend media/

# Configuration backup
tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" .env* nginx/ docker-compose*.yml

# Upload to S3 (optional)
aws s3 sync ${BACKUP_DIR} s3://your-bucket/backups/

# Clean old backups (keep 30 days)
find ${BACKUP_DIR} -mtime +30 -delete

echo "Backup completed: ${DATE}"
```

### Recovery Procedure

```bash
# 1. Stop services
docker-compose down

# 2. Restore database
gunzip < backup_20241106.sql.gz | docker exec -i binancebot_postgres psql -U binancebot binancebot

# 3. Restore media files
tar -xzf media_20241106.tar.gz -C backend/

# 4. Restart services
docker-compose up -d

# 5. Verify
docker-compose ps
curl http://localhost:8000/api/health/
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs binancebot_backend

# Common issues:
# 1. Database not ready → Wait for postgres health check
# 2. Port conflict → Check if port 8000 is in use
# 3. Environment variables missing → Verify .env file
```

### Database Connection Error

```bash
# Test database connectivity
docker exec binancebot_backend python manage.py dbshell

# If fails, check:
# 1. Postgres is running: docker ps | grep postgres
# 2. Credentials correct: Check .env file
# 3. Network connectivity: docker network ls
```

### Celery Worker Not Processing Tasks

```bash
# Check worker status
docker logs binancebot_celery_worker

# Common issues:
# 1. Redis not connected → Check CELERY_BROKER_URL
# 2. Tasks not registered → Restart worker
# 3. Memory exhausted → Increase Docker memory limit
```

### Frontend Build Fails

```bash
# Check Node version
docker exec binancebot_frontend node --version

# Clear cache and rebuild
docker-compose down
docker volume rm binancebot_node_modules
docker-compose up -d --build frontend
```

### SSL Certificate Issues

```bash
# Renew certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Reload Nginx
docker exec binancebot_nginx nginx -s reload
```

---

## Health Checks

### Create Health Check Endpoint

**backend/signals/views.py**:
```python
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """Health check endpoint for load balancers"""
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Check Redis
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')

        return JsonResponse({
            'status': 'healthy',
            'database': 'ok',
            'cache': 'ok'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)
```

### Monitor Health

```bash
# Add to crontab for alerting
*/5 * * * * curl -f http://localhost:8000/api/health/ || echo "Health check failed" | mail -s "Alert" admin@example.com
```

---

## Additional Resources

- [Technical Documentation](TECHNICAL_DOCUMENTATION.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)
- [Docker Documentation](https://docs.docker.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)

---

**Last Updated**: November 6, 2025
**Version**: 1.0.0
