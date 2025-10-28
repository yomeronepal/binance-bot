# Docker Configuration for Binance Trading Bot

Complete Docker setup for running the full-stack Binance Trading Bot application with backend, frontend, database, cache, and task queue.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │PostgreSQL│  │  Redis   │  │  Django  │             │
│  │   (DB)   │  │ (Cache)  │  │ Backend  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│                                    │                     │
│  ┌──────────┐  ┌──────────┐      │                     │
│  │  Celery  │  │  Celery  │◄─────┘                     │
│  │  Worker  │  │   Beat   │                             │
│  └──────────┘  └──────────┘                             │
│                                                          │
│  ┌──────────┐                                           │
│  │  React   │                                           │
│  │ Frontend │                                           │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

## Files

- `Dockerfile` - Django backend container
- `Dockerfile.frontend` - React frontend production container (nginx)
- `Dockerfile.frontend.dev` - React frontend development container (Vite)
- `docker-compose.yml` - Development environment
- `docker-compose.prod.yml` - Production environment
- `nginx.conf` - Frontend nginx configuration
- `nginx-proxy.conf` - Reverse proxy configuration (production)

## Services

### Development Environment

| Service | Port | Description |
|---------|------|-------------|
| **db** | 5432 | PostgreSQL database |
| **redis** | 6379 | Redis cache & message broker |
| **web** | 8000 | Django backend API |
| **frontend** | 5173 | React frontend (dev server with HMR) |
| **celery** | - | Celery worker for background tasks |
| **celery-beat** | - | Celery scheduler |

### Production Environment

| Service | Port | Description |
|---------|------|-------------|
| **nginx** | 80, 443 | Reverse proxy (frontend + backend) |
| **frontend** | - | React frontend (nginx) |
| **web** | - | Django backend (gunicorn) |
| Others | - | Same as development |

## Quick Start

### Development

```bash
# Navigate to docker directory
cd docker

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Stop all services
docker compose down
```

**Access:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Admin Panel: http://localhost:8000/admin

### Production

```bash
cd docker

# Build and start production services
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Create superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

**Access:**
- Application: http://localhost (via nginx proxy)
- API: http://localhost/api
- Admin: http://localhost/admin

## Environment Variables

Create `.env` file in `backend/` directory:

```env
# Django
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DATABASE_URL=postgres://binancebot:binancebot123@db:5432/binancebot
POSTGRES_DB=binancebot
POSTGRES_USER=binancebot
POSTGRES_PASSWORD=binancebot123

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440
```

## Docker Commands

### Build Services

```bash
# Build all services
docker compose build

# Build specific service
docker compose build web
docker compose build frontend

# Build without cache
docker compose build --no-cache
```

### Start/Stop Services

```bash
# Start all services
docker compose up

# Start in detached mode
docker compose up -d

# Start specific services
docker compose up db redis web

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### View Logs

```bash
# All services
docker compose logs

# Follow logs
docker compose logs -f

# Specific service
docker compose logs web
docker compose logs frontend

# Last 100 lines
docker compose logs --tail=100
```

### Execute Commands

```bash
# Django management commands
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell

# Access container shell
docker compose exec web sh
docker compose exec frontend sh

# Install npm packages
docker compose exec frontend npm install package-name
```

### Service Management

```bash
# Restart service
docker compose restart web
docker compose restart frontend

# Stop service
docker compose stop celery

# Start service
docker compose start celery

# View service status
docker compose ps

# View resource usage
docker stats
```

## Development Workflow

### Backend Development

1. **Make changes** to Python files in `../backend/`
2. **Changes are live-reloaded** (volume mounted)
3. **Run migrations** if models changed:
   ```bash
   docker compose exec web python manage.py makemigrations
   docker compose exec web python manage.py migrate
   ```

### Frontend Development

1. **Make changes** to React files in `../client/src/`
2. **Hot reload** works automatically (Vite HMR)
3. **Install new packages**:
   ```bash
   docker compose exec frontend npm install package-name
   ```
4. **View logs** for errors:
   ```bash
   docker compose logs -f frontend
   ```

### Database Access

```bash
# PostgreSQL shell
docker compose exec db psql -U binancebot -d binancebot

# Run SQL commands
docker compose exec db psql -U binancebot -d binancebot -c "SELECT * FROM users;"

# Backup database
docker compose exec db pg_dump -U binancebot binancebot > backup.sql

# Restore database
docker compose exec -T db psql -U binancebot -d binancebot < backup.sql
```

### Redis Access

```bash
# Redis CLI
docker compose exec redis redis-cli

# Check keys
docker compose exec redis redis-cli keys '*'

# Clear all data
docker compose exec redis redis-cli FLUSHALL
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs service-name

# Check service status
docker compose ps

# Rebuild service
docker compose up -d --build service-name
```

### Database Connection Issues

```bash
# Check database is running
docker compose ps db

# Check database logs
docker compose logs db

# Restart database
docker compose restart db

# Reset database (CAUTION: deletes all data)
docker compose down -v
docker compose up -d db
```

### Frontend Not Loading

```bash
# Check frontend logs
docker compose logs -f frontend

# Check if port 5173 is available
netstat -an | grep 5173

# Rebuild frontend
docker compose up -d --build frontend

# Clear node_modules cache
docker compose down
docker volume rm docker_node_modules_volume  # Named volume for node_modules
docker compose up -d frontend
```

### Frontend Missing Dependencies

If you see errors like "The following dependencies are imported but could not be resolved":

```bash
# Install missing dependencies on host first
cd ../client
npm install

# Then rebuild the frontend container
cd ../docker
docker compose build --no-cache frontend
docker compose up -d frontend
```

The frontend uses a named volume `node_modules_volume` to persist npm packages between container restarts while allowing hot reload of source code.

### Permission Issues

```bash
# Fix file permissions (Linux/Mac)
sudo chown -R $USER:$USER ../backend
sudo chown -R $USER:$USER ../client

# Windows: Run Docker Desktop as Administrator
```

### Port Already in Use

Edit `docker-compose.yml` and change port mappings:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

## Production Deployment

### Pre-deployment Checklist

- [ ] Set `DEBUG=False` in backend `.env`
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Update `ALLOWED_HOSTS` with your domain
- [ ] Configure SSL certificates
- [ ] Set strong database passwords
- [ ] Configure CORS settings
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy

### SSL/HTTPS Setup

1. **Get SSL certificates** (Let's Encrypt, Cloudflare, etc.)
2. **Add certificates** to `nginx-proxy.conf`
3. **Update nginx configuration** to enable HTTPS
4. **Update frontend** `.env` with `https://` URLs

### Scaling

```bash
# Scale celery workers
docker compose up -d --scale celery=4

# Scale with specific resources
docker compose up -d --scale celery=4 --cpus=2 --memory=2g
```

### Health Checks

```bash
# Check all service health
docker compose ps

# Manual health check
curl http://localhost:8000/api/health/
curl http://localhost/health  # nginx
```

## Volumes

### Development Volumes

- `postgres_data` - Database persistence
- `static_volume` - Static files
- `media_volume` - User uploads
- `node_modules_volume` - Frontend npm packages (persisted across restarts)
- `../backend` - Backend source (mounted for hot reload)
- `../client` - Frontend source (mounted for hot reload)

### Backup Volumes

```bash
# Backup all volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .

# Restore volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /data
```

## Network

All services run on `binancebot_network` bridge network:
- Services can communicate using service names (e.g., `web`, `db`, `redis`)
- Isolated from other Docker networks
- Port mapping exposes services to host

## Performance Optimization

### Production Settings

1. **Use gunicorn** instead of Django dev server
2. **Enable nginx caching** for static files
3. **Use Redis** for session storage
4. **Configure CDN** for static assets
5. **Use connection pooling** for database

### Resource Limits

Add to `docker-compose.yml`:
```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Monitoring

```bash
# Real-time resource usage
docker stats

# Service health
docker compose ps

# Container inspection
docker inspect binancebot_web
```

## Cleanup

```bash
# Remove stopped containers
docker compose down

# Remove all (including volumes)
docker compose down -v

# Remove all Docker data
docker system prune -a --volumes
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Build and test
  run: |
    cd docker
    docker compose build
    docker compose up -d
    docker compose exec -T web python manage.py test
    docker compose down
```

## Support

For issues:
- Check logs: `docker compose logs -f`
- Inspect service: `docker compose ps`
- View networks: `docker network ls`
- Check volumes: `docker volume ls`

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Docker Guide](https://docs.djangoproject.com/en/stable/howto/deployment/)
