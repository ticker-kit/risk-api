FROM python:3.11.9-slim

WORKDIR /app

# Copy and install requirements first (for better caching)
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the application code
COPY app/ ./app/
COPY alembic/ ./alembic/

EXPOSE 10000

# Create a startup script that runs migrations first
RUN echo '#!/bin/bash\n\
alembic upgrade head\n\
exec uvicorn app.main:app --host 0.0.0.0 --port 10000\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]