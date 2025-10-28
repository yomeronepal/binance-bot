# Binance Trading Bot - Full Stack Application

Complete trading bot platform with Django REST API backend and React frontend, fully containerized with Docker.

## 🏗️ Project Structure

```
binance-bot/
├── backend/           # Django REST API
│   ├── api/           # REST endpoints wrapper
│   ├── users/         # Authentication & profiles
│   ├── signals/       # Trading signals
│   ├── scanner/       # Binance data ingestion
│   ├── billing/       # Stripe integration
│   ├── websocket/     # Django Channels
│   └── config/        # Django settings
├── client/            # React Frontend
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── pages/       # Page components
│   │   ├── store/       # Zustand state
│   │   ├── services/    # API layer
│   │   └── routes/      # Router config
│   └── package.json
├── docker/            # Docker configuration
│   ├── Dockerfile            # Backend container
│   ├── Dockerfile.frontend   # Frontend production
│   ├── docker-compose.yml    # Development
│   └── docker-compose.prod.yml  # Production
└── README.md          # This file
```

## 🚀 Quick Start with Docker

### Prerequisites
- Docker Desktop or Docker Engine + Docker Compose
- Git (optional)

### Development Setup

```bash
# Navigate to docker directory
cd docker

# Start all services (backend, frontend, database, redis)
docker compose up -d

# Run database migrations (first time only)
docker compose exec web python manage.py migrate

# Create admin user (first time only)
docker compose exec web python manage.py createsuperuser
```

**Note**: The first time you run the frontend container, it will install all npm dependencies. This may take a few minutes.

**Access the application:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api
- **Admin Panel**: http://localhost:8000/admin

### Production Setup

```bash
cd docker

# Start production services
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations and collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

## 🛠️ Tech Stack

### Backend
- **Django 5.0.1** - Web framework
- **Django REST Framework** - RESTful API
- **SimpleJWT** - JWT authentication
- **Django Channels** - WebSocket support
- **PostgreSQL 15** - Database
- **Redis 7** - Cache & message broker
- **Celery** - Background tasks

### Frontend
- **React 18** + **Vite** - UI framework
- **TailwindCSS** - Styling
- **Zustand** - State management
- **React Router v6** - Routing
- **Axios** - HTTP client
- **Recharts** - Charts & visualization

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy (production)

## 📋 Features

### Implemented ✅
- JWT authentication with auto token refresh
- User registration and login
- Protected routes
- Trading signal CRUD operations
- Signal list and detail views with charts
- Real-time WebSocket infrastructure
- Responsive design with dark mode
- Full Docker setup (dev & prod)

### In Progress 🚧
- Binance API integration
- Signal generation algorithms
- Stripe payment processing
- Email notifications
- Advanced filtering and search

## 🐳 Docker Services

| Service | Port | Description |
|---------|------|-------------|
| **frontend** | 5173 | React app (dev) / 80 (prod) |
| **web** | 8000 | Django API |
| **db** | 5432 | PostgreSQL database |
| **redis** | 6379 | Redis cache |
| **celery** | - | Background task worker |
| **celery-beat** | - | Task scheduler |

## 📚 Documentation

- **Docker Setup**: See [docker/README.md](docker/README.md)
- **Backend API**: See [backend/SETUP_COMPLETE.md](backend/SETUP_COMPLETE.md)
- **Frontend**: See [client/README.md](client/README.md)
- **Project Overview**: See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)

## 🔧 Development Without Docker

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```

### Frontend

```bash
cd client

# Install dependencies
npm install

# Start dev server
npm run dev
```

## 🌐 API Endpoints

### Authentication
- `POST /api/users/register/` - Register
- `POST /api/users/login/` - Login
- `POST /api/users/token/refresh/` - Refresh token
- `GET /api/users/profile/` - Get profile

### Signals
- `GET /api/signals/` - List signals
- `GET /api/signals/:id/` - Get signal
- `POST /api/signals/` - Create signal
- `PUT /api/signals/:id/` - Update signal
- `DELETE /api/signals/:id/` - Delete signal

### Health
- `GET /api/health/` - API health check

## 🎨 Frontend Routes

- `/login` - User login
- `/register` - User registration
- `/dashboard` - Main dashboard
- `/signals` - Signal list
- `/signals/:id` - Signal detail

## ⚙️ Environment Variables

### Backend (`.env` in `backend/`)
```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://binancebot:binancebot123@db:5432/binancebot
REDIS_URL=redis://redis:6379/0
```

### Frontend (`.env` in `client/`)
```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

## 🔍 Common Commands

### Docker

```bash
# View all containers
docker compose ps

# View logs
docker compose logs -f

# Restart service
docker compose restart web

# Stop all services
docker compose down

# Remove everything including volumes
docker compose down -v
```

### Django

```bash
# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Django shell
docker compose exec web python manage.py shell

# Run tests
docker compose exec web python manage.py test
```

### Frontend

```bash
# Install package
docker compose exec frontend npm install package-name

# View logs
docker compose logs -f frontend

# Restart
docker compose restart frontend
```

## 🐛 Troubleshooting

### Port Already in Use
Edit `docker/docker-compose.yml` and change port mappings.

### Database Connection Failed
```bash
docker compose restart db
docker compose logs db
```

### Frontend Not Loading
```bash
docker compose logs -f frontend
docker compose restart frontend
```

### Reset Everything
```bash
docker compose down -v
docker compose up -d --build
docker compose exec web python manage.py migrate
```

## 📖 Detailed Guides

- **Backend Setup**: [backend/SETUP_COMPLETE.md](backend/SETUP_COMPLETE.md)
- **Frontend Setup**: [client/README.md](client/README.md)
- **Docker Guide**: [docker/README.md](docker/README.md)
- **Full Project Overview**: [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)

## 🚦 Testing

### Backend Tests
```bash
docker compose exec web python manage.py test
```

### Frontend Tests
```bash
cd client
npm run test  # (to be configured)
```

## 📦 Building for Production

```bash
cd docker

# Build and start production stack
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

## 🔐 Security Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use strong database passwords
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Configure security headers
- [ ] Set up monitoring and logging

## 🛣️ Roadmap

### Phase 1: Foundation ✅
- [x] Django backend with JWT auth
- [x] React frontend with routing
- [x] Docker containerization
- [x] Basic CRUD operations

### Phase 2: Integration 🚧
- [ ] Binance API integration
- [ ] Real-time WebSocket updates
- [ ] Signal generation algorithms
- [ ] User notification system

### Phase 3: Premium Features
- [ ] Stripe payment integration
- [ ] Advanced analytics
- [ ] Backtesting functionality
- [ ] Mobile app

### Phase 4: Scaling
- [ ] Kubernetes deployment
- [ ] Load balancing
- [ ] Caching optimization
- [ ] Performance monitoring

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

[Add your license here]

## 💬 Support

For issues or questions:
- **Backend**: Check [Django docs](https://docs.djangoproject.com/)
- **Frontend**: Check [React docs](https://react.dev/) and [Vite docs](https://vitejs.dev/)
- **Docker**: Check [Docker docs](https://docs.docker.com/)

## ⭐ Acknowledgments

- Django REST Framework
- React & Vite teams
- TailwindCSS
- Recharts
- All open source contributors

---

**Status**: ✅ Ready for Development | 🚀 Production Ready (with configuration)
