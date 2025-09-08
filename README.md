# Risk API

A comprehensive **FastAPI-based risk metrics API** that provides portfolio management and real-time price tracking capabilities. This service enables users to manage investment portfolios, track market data, calculate risk metrics, and receive real-time price updates through Redis pub/sub messaging.

## What it does

The Risk API is designed for financial applications and portfolio management systems. Key features include:

- **Portfolio Management**: Create, read, update, and delete investment positions
- **Real-time Price Tracking**: Integrate with yFinance for live market data
- **Risk Metrics Calculation**: Analyze portfolio risk and performance metrics  
- **User Authentication**: Secure JWT-based user management
- **Redis Pub/Sub Integration**: Real-time price updates and caching
- **Multi-environment Support**: Development (FakeRedis), Docker, and production modes

## Architecture

This service is part of a larger microservices architecture that handles:
- Portfolio management (add/update/delete positions)
- Price caching and updates via Redis pub/sub
- User authentication and management
- Risk metrics calculation

## Tech Stack

- **FastAPI** - Web framework
- **PostgreSQL** - Database (production)
- **SQLite** - Database (local development)
- **Redis** - Pub/sub messaging and caching (with FakeRedis for local dev)
- **SQLAlchemy** - ORM with Alembic for migrations
- **yFinance** - Market data integration
- **JWT** - Authentication

## Getting Started

### Prerequisites

- Python 3.9+ 
- Git

### Clone and Run

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ticker-kit/risk-api.git
   cd risk-api
   ```

2. **Install dependencies** (takes ~45 seconds):
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Set up environment**:
   ```bash
   cp env.example .env
   mkdir -p data
   ```

4. **Start the application**:
   ```bash
   uvicorn app.main:app --env-file .env --reload --port 10000
   ```

5. **Access the API**:
   - API: http://localhost:10000
   - Interactive docs: http://localhost:10000/docs
   - Health check: http://localhost:10000/healthz

The application will run in development mode using SQLite database and FakeRedis (no external Redis server required).

## Advanced Setup

### Environment Configuration

Copy `env.example` to `.env` and configure for different environments:

**Development (Local - Default)**:
```bash
ENV=dev                    # Uses FakeRedis (no external Redis needed)
DATABASE_URL=sqlite:///./data/risk.db
JWT_SECRET_KEY=your-secret-key
CORS_ORIGIN=http://localhost:3000
```

**Docker Deployment**:
```bash
ENV=docker               # Uses Redis container
DATABASE_URL=postgresql://user:password@localhost:5432/db
JWT_SECRET_KEY=your-secret-key
CORS_ORIGIN=http://localhost:3000
```

### Docker Setup

1. **Create environment files**:
   - `.env.docker.postgres`:
     ```
     POSTGRES_USER=risk_user
     POSTGRES_PASSWORD=risk_password
     POSTGRES_DB=risk_db
     ```
   
   - `.env.docker.api`:
     ```
     ENV=docker
     DATABASE_URL=postgresql://risk_user:risk_password@risk-postgres:5432/risk_db
     JWT_SECRET_KEY=docker-super-secret-jwt-key-for-testing
     CORS_ORIGIN=http://localhost:3000
     ```

2. **Start with Docker Compose**:
```bash
docker compose up --build
```

### Local Development (Alternative)

If you prefer manual setup instead of the quick start above:

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment  
cp env.example .env
mkdir -p data

# Start with custom configuration
uvicorn app.main:app --env-file .env --reload --port 10000
```

## API Endpoints

### Portfolio
- `GET /portfolio` - Get user portfolio
- `POST /portfolio` - Add position
- `PUT /portfolio/{symbol}` - Update position
- `DELETE /portfolio/{symbol}` - Remove position

### Risk & Pricing

- `GET /search_ticker` - Search tickers
- `POST /trigger-price-update/{ticker}` - Trigger price fetch

### Authentication
- `POST /register` - Register user
- `POST /login` - Login user
- `GET /me` - Get current user

### System
- `GET /healthz` - Health check
- `GET /redis-info` - Redis connection status

## Redis Integration

The service uses Redis for:
- **Pub/sub messaging** - Ticker update events
- **Price caching** - Latest price storage
- **Multi-environment support**:
  - `ENV=dev` - FakeRedis (no external Redis needed)
  - `ENV=docker` - Redis container
  - `ENV=prod` - Upstash Redis (cloud)

## Development

```bash
# Run locally with hot reload
uvicorn app.main:app --env-file .env --reload --port 10000

# Run tests
pytest

# View logs
docker-compose logs -f risk-api
```

## Environment Variables

Required:
- `ENV` - Environment (dev/docker/prod)
- `DATABASE_URL` - PostgreSQL connection
- `JWT_SECRET_KEY` - JWT signing key
- `CORS_ORIGIN` - CORS allowed origins

Optional (prod only):
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_USER`, `REDIS_PASSWORD` - Redis connection
- `REDIS_DOMAIN`, `REDIS_TLS` - Redis URL configuration