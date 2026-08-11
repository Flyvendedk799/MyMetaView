# Frontend Development & Deployment Guide

This document covers frontend development, build, and deployment for the Preview SaaS Dashboard.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Heroicons** - Icon library

## Development Setup

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
npm install
```

### Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Environment Variables

Create a `.env` file in the project root:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STRIPE_PRICE_TIER_BASIC=price_xxx
VITE_STRIPE_PRICE_TIER_PRO=price_xxx
VITE_STRIPE_PRICE_TIER_AGENCY=price_xxx
VITE_FRONTEND_BASE_URL=http://localhost:5173
```

## Building for Production

### Build Command

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

### Build Optimizations

- TypeScript compilation with type checking
- Tree-shaking (removes unused code)
- Minification (JavaScript and CSS)
- Code splitting
- Asset optimization

### Production Environment Variables

Set these in your deployment platform:

- `VITE_API_BASE_URL` - Backend API URL (e.g., `https://api.example.com`)
- `VITE_STRIPE_PRICE_TIER_BASIC` - Stripe price ID for Basic tier
- `VITE_STRIPE_PRICE_TIER_PRO` - Stripe price ID for Pro tier
- `VITE_STRIPE_PRICE_TIER_AGENCY` - Stripe price ID for Agency tier
- `VITE_FRONTEND_BASE_URL` - Frontend URL (e.g., `https://app.example.com`)

## Deployment

### Option 1: Railway Static Service

1. Create a new static service in Railway
2. Set build command: `npm ci && npm run build`
3. Set output directory: `dist`
4. Set environment variables
5. Deploy

### Option 2: Docker Deployment

Build and run:

```bash
docker build -f Dockerfile.frontend -t preview-frontend .
docker run -p 80:80 preview-frontend
```

### Option 3: Traditional Hosting

1. Build the application: `npm run build`
2. Upload `dist/` contents to your web server
3. Configure server to serve `index.html` for all routes (SPA routing)
4. Set environment variables in build-time or runtime config

## Project Structure

```
src/
├── api/              # API client functions
├── components/      # Reusable React components
│   ├── ui/          # UI primitives (Button, Card, Input, etc.)
│   ├── layout/      # Layout components (Header, Sidebar, Footer)
│   └── error/       # Error boundary components
├── hooks/           # Custom React hooks
├── pages/           # Page components
│   ├── admin/       # Admin pages
│   └── ...          # User-facing pages
├── router/          # React Router configuration
├── theme.ts         # Design tokens
└── main.tsx         # Application entry point
```

## Key Features

- **Authentication**: JWT-based auth with localStorage token storage
- **Protected Routes**: Route guards for authenticated/paid/admin users
- **Organization Management**: Multi-tenant organization switching
- **Real-time Updates**: Job status polling for async operations
- **Error Boundaries**: Graceful error handling
- **Responsive Design**: Mobile-friendly layouts

## API Integration

The frontend communicates with the backend via REST API:

- Base URL: Configured via `VITE_API_BASE_URL`
- Authentication: Bearer token in `Authorization` header
- Organization context: `X-Organization-ID` header

See `src/api/client.ts` for API client implementation.

## Performance Optimizations

- Lazy loading for images (`loading="lazy"`)
- Skeleton loaders for better perceived performance
- Debounced filter inputs
- Client-side caching for analytics data
- React.memo and useMemo for expensive components

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Troubleshooting

### Build Errors

- Ensure Node.js 18+ is installed
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npm run build` will show type errors

### API Connection Issues

- Verify `VITE_API_BASE_URL` is set correctly
- Check CORS settings on backend
- Verify API is accessible from frontend domain

### Environment Variables Not Working

- Vite requires `VITE_` prefix for environment variables
- Rebuild after changing environment variables
- Check `.env` file is in project root

