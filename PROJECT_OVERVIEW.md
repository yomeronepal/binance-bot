# Binance Trading Bot - Complete Project

Full-stack trading bot platform with Django backend and React frontend, segregated for clean architecture.

## Project Structure

```
binance-bot/
├── backend/              # Django REST API
│   ├── api/              # REST endpoints wrapper
│   ├── users/            # Authentication & profiles
│   ├── signals/          # Trading signals
│   ├── scanner/          # Binance data ingestion
│   ├── billing/          # Stripe integration
│   ├── websocket/        # Django Channels
│   ├── config/           # Django settings
│   ├── manage.py
│   ├── requirements.txt
│   └── .env              # Backend environment variables
│
├── client/               # React Frontend
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── pages/        # Pages (Dashboard, Signals, Auth)
│   │   ├── store/        # Zustand state management
│   │   ├── services/     # API layer (axios)
│   │   ├── routes/       # React Router setup
│   │   └── App.jsx
│   ├── package.json
│   └── .env              # Frontend environment variables
│
└── docker/               # Docker configuration
    ├── Dockerfile        # Django app container
    └── docker-compose.yml # Full stack orchestration
```

## Tech Stack

### Backend
- **Django 5.0.1** - Web framework
- **Django REST Framework** - API
- **SimpleJWT** - JWT authentication
- **Django Channels** - WebSocket support
- **PostgreSQL** - Database
- **Redis** - Cache & message broker
- **Celery** - Background tasks
- **Docker** - Containerization

### Frontend
- **React 18** + **Vite** - UI framework
- **TailwindCSS** - Styling
- **Zustand** - State management
- **React Router** - Routing
- **Axios** - HTTP client
- **Recharts** - Charts

## Quick Start

### Backend

```bash
cd backend

# Install dependencies (in virtual environment)
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Backend will run at: http://localhost:8000

### Frontend

```bash
cd client

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will run at: http://localhost:5173

### Docker (Recommended)

```bash
cd docker

# Start all services
docker compose up -d

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
```

Services:
- **Backend API**: http://localhost:8000
- **Frontend**: Build separately and serve
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Environment Variables

### Backend (.env in `backend/`)
```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://binancebot:binancebot123@db:5432/binancebot
REDIS_URL=redis://redis:6379/0
```

### Frontend (.env in `client/`)
```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

## API Endpoints

### Authentication
- `POST /api/users/register/` - Register user
- `POST /api/users/login/` - Login (get JWT tokens)
- `POST /api/users/token/refresh/` - Refresh access token
- `GET /api/users/profile/` - Get user profile

### Signals
- `GET /api/signals/` - List all signals
- `GET /api/signals/:id/` - Get signal detail
- `POST /api/signals/` - Create signal
- `PUT /api/signals/:id/` - Update signal
- `DELETE /api/signals/:id/` - Delete signal

### Health Check
- `GET /api/health/` - API health status

## Frontend Pages

### Public Routes
- `/login` - User login
- `/register` - User registration

### Protected Routes (Authenticated)
- `/dashboard` - Overview with statistics
- `/signals` - List all signals with filtering
- `/signals/:id` - Signal detail with chart

## Features

### Implemented ✅
- JWT authentication with auto-refresh
- User registration and login
- Protected routes
- Signal CRUD operations (backend ready)
- Signal list and detail views
- Interactive price charts (Recharts)
- Real-time WebSocket support (infrastructure ready)
- Responsive design with TailwindCSS
- Dark mode support
- Docker containerization

### To Be Implemented 🚧
- Binance API integration
- Signal generation algorithms
- Stripe payment processing
- Email notifications
- User preferences
- Advanced filtering and search
- Export functionality
- Unit and integration tests

## Development Workflow

### Backend Development
1. Create/update models in app
2. Make migrations: `python manage.py makemigrations`
3. Apply migrations: `python manage.py migrate`
4. Update serializers and views
5. Add URL routes
6. Test endpoints

### Frontend Development
1. Create components in `src/components/`
2. Add pages in `src/pages/`
3. Update store in `src/store/` if needed
4. Add routes in `src/routes/AppRouter.jsx`
5. Test in browser

### Full Stack Testing
1. Start backend: `cd backend && python manage.py runserver`
2. Start frontend: `cd client && npm run dev`
3. Test authentication flow
4. Test protected routes
5. Test API integration

## Production Deployment

### Backend
```bash
cd backend
python manage.py collectstatic
gunicorn config.wsgi:application
```

### Frontend
```bash
cd client
npm run build
# Serve dist/ folder with nginx or similar
```

### Docker Production
```bash
cd docker
docker compose -f docker-compose.prod.yml up -d
```

## Documentation

- **Backend**: See `backend/README.md` (from SETUP_COMPLETE.md)
- **Frontend**: See `client/README.md`
- **API**: See backend code for endpoint documentation

## Testing

### Backend
```bash
cd backend
python manage.py test
```

### Frontend
```bash
cd client
npm run test  # (to be set up)
```

## Contributing

1. Follow existing code structure
2. Write clean, documented code
3. Test changes before committing
4. Follow naming conventions

## Troubleshooting

### Backend Issues
- Verify PostgreSQL is running
- Check `.env` file configuration
- Run migrations if models changed
- Check Django logs

### Frontend Issues
- Clear `node_modules` and reinstall
- Verify backend is running at correct URL
- Check browser console for errors
- Verify `.env` file configuration

### Docker Issues
- Rebuild containers: `docker compose build`
- Check logs: `docker compose logs -f`
- Reset volumes: `docker compose down -v`

## Next Steps

1. **Binance Integration**
   - Add API client in `scanner` app
   - Implement data fetching
   - Create signal generation logic

2. **Payment Processing**
   - Implement Stripe webhooks
   - Add subscription tiers
   - Create billing dashboard

3. **Advanced Features**
   - Add notification system
   - Implement advanced analytics
   - Create admin dashboard
   - Add backtesting functionality

4. **Testing & CI/CD**
   - Write comprehensive tests
   - Set up GitHub Actions
   - Configure staging environment
   - Set up monitoring

## License

[Your License Here]

## Support

For issues or questions:
- Backend: Check Django documentation
- Frontend: Check React/Vite documentation
- Docker: Check Docker Compose documentation
