# Binance Trading Bot - Frontend

Modern React frontend built with Vite, TailwindCSS, Zustand, and Recharts for trading signal visualization.

## Tech Stack

- **React 18** + **Vite** - Fast development with HMR
- **TailwindCSS** - Utility-first CSS with dark mode
- **Zustand** - Lightweight state management
- **React Router v6** - Client-side routing with protected routes
- **Axios** - HTTP client with interceptors
- **Recharts** - Chart library for signal visualization
- **WebSocket** - Real-time updates support

## Quick Start

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Start development server
npm run dev
```

App will be available at http://localhost:5173

## Environment Variables

```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/signals/
```

## Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── common/       # SignalCard, etc.
│   ├── layout/       # Layout, Header, Footer
│   └── charts/       # SignalChart
├── pages/            # Page components
│   ├── auth/         # Login, Register
│   ├── dashboard/    # Dashboard
│   └── signals/      # SignalList, SignalDetail
├── store/            # Zustand stores
│   ├── useAuthStore.js
│   └── useSignalStore.js
├── services/         # API services
│   ├── api.js
│   ├── authService.js
│   └── signalService.js
├── routes/           # Router configuration
├── hooks/            # Custom hooks
└── utils/            # Utilities
```

## Features

### Authentication
- JWT-based login/register
- Automatic token refresh
- Protected routes
- Persistent sessions

### Dashboard
- Overview statistics
- Recent signals grid
- Real-time updates (WebSocket ready)
- Responsive design

### Signals
- List view with filtering (BUY/SELL/HOLD, Active/Executed)
- Detail view with price chart
- Entry/Target/Stop Loss visualization
- Risk/Reward analysis
- Confidence indicators

### Charts
- Interactive price charts with Recharts
- Reference lines for entry, target, and stop loss
- Responsive and customizable
- Mock data support for development

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |

## API Integration

### Endpoints

**Authentication:**
- `POST /api/users/register/` - Register
- `POST /api/users/login/` - Login
- `POST /api/users/token/refresh/` - Refresh token
- `GET /api/users/profile/` - Get profile

**Signals:**
- `GET /api/signals/` - List signals
- `GET /api/signals/:id/` - Get signal
- `POST /api/signals/` - Create signal
- `PUT /api/signals/:id/` - Update signal
- `DELETE /api/signals/:id/` - Delete signal

### WebSocket

Real-time updates via WebSocket:
```javascript
const { connectWebSocket, disconnectWebSocket } = useSignalStore();

// Connect
connectWebSocket();

// Auto-reconnect on disconnect
```

## Mock Data

The app includes mock signal data for development when the backend is unavailable. Toggle `useMockData` in components to switch between real and mock data.

## Styling

### TailwindCSS Components

Custom utility classes:
- `.btn`, `.btn-primary`, `.btn-secondary` - Buttons
- `.card` - Card containers
- `.input`, `.label` - Form elements

### Color Palette
- **Primary**: Blue (#0ea5e9)
- **Success**: Green (#10b981)
- **Danger**: Red (#ef4444)
- **Warning**: Orange (#f59e0b)

## Building for Production

```bash
npm run build
npm run preview  # Test production build locally
```

Deploy the `dist/` folder to your hosting service.

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Troubleshooting

**API Connection Issues:**
1. Verify backend is running at `http://localhost:8000`
2. Check `.env` file configuration
3. Check browser console for CORS errors

**Build Errors:**
```bash
rm -rf node_modules && npm install  # Reinstall dependencies
npm run build                        # Try build again
```

## Next Steps

- [ ] Add toast notifications
- [ ] Implement signal creation form
- [ ] Add user profile/settings page
- [ ] Add unit tests (Vitest)
- [ ] Implement advanced filtering
- [ ] Add export functionality

## Resources

- [React Docs](https://react.dev/)
- [Vite Docs](https://vitejs.dev/)
- [TailwindCSS Docs](https://tailwindcss.com/)
- [Zustand Docs](https://github.com/pmndrs/zustand)
- [Recharts Docs](https://recharts.org/)
