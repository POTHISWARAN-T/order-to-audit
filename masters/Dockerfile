FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

# Creates the tables, loads the benchmark data and demo logins, then starts the server
CMD ["sh", "-c", "python manage.py setup_demo && python manage.py runserver 0.0.0.0:8000"]