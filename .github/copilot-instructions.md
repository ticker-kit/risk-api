# Risk API - GitHub Copilot Instructions

Risk API is a FastAPI-based risk metrics API with Redis pub/sub integration for portfolio management and price tracking.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Tech Stack Overview
- **FastAPI** - Web framework
- **PostgreSQL** - Database (production)
- **SQLite** - Database (local development)  
- **Redis** - Pub/sub messaging and caching (with FakeRedis for local dev)
- **SQLAlchemy** - ORM with Alembic for migrations
- **yFinance** - Market data integration
- **JWT** - Authentication

## Working Effectively

### Bootstrap and Setup Process

**CRITICAL BUILD TIMES:** Package installation takes approximately 45 seconds. Application startup is instantaneous (< 5 seconds). **NEVER CANCEL** these operations.

#### Local Development (Recommended for Development)
**ALWAYS** use the local development setup for coding and testing:

1. **Install Python dependencies** (takes ~45 seconds, NEVER CANCEL):
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Create environment file**:
   ```bash
   cp env.example .env
   ```
   
3. **Configure .env for local development**:
   ```
   ENV=dev
   DATABASE_URL=sqlite:///./data/risk.db
   JWT_SECRET_KEY=your-super-secret-jwt-key-change-this
   CORS_ORIGIN=http://localhost:3000
   RISK_WORKER_URL=http://localhost:8000
   WORKER_SECRET=your-shared-secret-key-change-this
   ```

4. **Create data directory**:
   ```bash
   mkdir -p data
   ```

5. **Start the application**:
   ```bash
   uvicorn app.main:app --env-file .env --reload --port 10000
   ```

The application will be available at http://localhost:10000

#### Docker Setup (Deployment/Integration Testing)
**WARNING:** Docker setup fails in environments with SSL certificate issues or firewall restrictions for PyPI access.

1. **Create required environment files**:
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
     RISK_WORKER_URL=http://localhost:8000
     WORKER_SECRET=docker-shared-secret-key-for-testing
     ```

2. **Start with Docker Compose** (build takes 3-5 minutes, NEVER CANCEL):
   ```bash
   docker compose up --build --timeout 300
   ```

**Note:** Use `docker compose` (with space) not `docker-compose`.

### Database Management

**CRITICAL:** Database migrations currently have issues with SQLite. The application will work without running migrations manually as it uses SQLModel for automatic table creation.

- **Check migration status**: `alembic current`
- **View migration history**: `alembic history`
- **DO NOT run** `alembic upgrade head` - this currently fails with missing table errors

### Key Application URLs and Endpoints

When the application is running locally on port 10000:

- **Health check**: http://localhost:10000/healthz → `{"status":"ok"}`
- **Root endpoint**: http://localhost:10000/ → `{"message":"Welcome to the Risk API"}`
- **API Documentation**: http://localhost:10000/docs (Interactive Swagger UI)
- **OpenAPI Schema**: http://localhost:10000/openapi.json

### Testing and Validation

**VALIDATION SCENARIOS** - Always test after making changes:

1. **Application startup test**:
   ```bash
   uvicorn app.main:app --env-file .env --reload --port 10000
   ```
   Verify: No startup errors, Redis FakeRedis connection successful

2. **Health endpoint test**:
   ```bash
   curl -s http://localhost:10000/healthz
   ```
   Expected: `{"status":"ok"}`

3. **API documentation test**:
   Navigate to http://localhost:10000/docs and verify the Swagger interface loads

4. **Basic API functionality**:
   ```bash
   curl -s http://localhost:10000/
   ```
   Expected: `{"message":"Welcome to the Risk API"}`

**Note:** External API endpoints (ticker search, price updates) may fail in restricted network environments but this is expected.

## Environment Configuration

### Three Environment Modes:
- `ENV=dev` - Uses FakeRedis (no external Redis required)
- `ENV=docker` - Uses Redis container via Docker Compose  
- `ENV=prod` - Uses Upstash Redis (cloud service)

### Required Environment Variables:
- `ENV` - Environment mode (dev/docker/prod)
- `DATABASE_URL` - Database connection string
- `JWT_SECRET_KEY` - JWT signing key
- `CORS_ORIGIN` - CORS allowed origins

## Project Structure Navigation

### Key Directories:
- `app/` - Main application code
  - `main.py` - FastAPI application entry point
  - `routes/` - API route handlers (portfolio, user, risk)
  - `models/` - Data models and schemas
  - `config.py` - Configuration management
  - `redis_service.py` - Redis/FakeRedis integration
  - `auth.py` - JWT authentication
- `alembic/` - Database migration files
- `static/` - Static assets (favicon, etc.)

### Important Files to Check After Changes:
- Always check `app/main.py` when modifying application startup
- Always check route files in `app/routes/` when modifying API endpoints
- Always check `app/models/` when modifying data structures
- Always check `app/config.py` when modifying environment configuration

## Common Development Workflows

### Making API Changes:
1. Start local development server with `--reload` flag
2. Modify route files in `app/routes/`
3. Test changes automatically reload in browser
4. Validate endpoints via http://localhost:10000/docs

### Environment Issues:
- **SSL/Certificate errors in Docker**: Expected in restricted environments, use local development instead
- **Redis connection fails**: Set `ENV=dev` to use FakeRedis
- **Database migration errors**: Skip migrations, app creates tables automatically

## Known Limitations
- Database migrations are currently broken - app works without them
- Docker build fails in environments with SSL certificate restrictions  
- yFinance ticker search requires external network access
- No test suite currently exists in the repository
- No linting configuration present

## CI/CD Notes
No GitHub Actions or CI configuration exists in this repository. All validation must be done manually using the steps outlined above.