FROM python:3.11.9-slim

WORKDIR /app

# Copy and install requirements first (for better caching)
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project (including alembic folder, alembic.ini, and all files)
COPY . .

EXPOSE 10000

# Create a robust startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Waiting for database to be ready..."\n\
python -c "\n\
import time\n\
import psycopg2\n\
from app.config import settings\n\
\n\
while True:\n\
    try:\n\
        conn = psycopg2.connect(settings.database_url)\n\
        conn.close()\n\
        print(\"Database is ready!\")\n\
        break\n\
    except Exception as e:\n\
        print(f\"Database not ready: {e}\")\n\
        time.sleep(2)\n\
"\n\
\n\
echo "Running database migrations..."\n\
alembic upgrade head\n\
\n\
echo "Starting application..."\n\
exec uvicorn app.main:app --host 0.0.0.0 --port 10000\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]