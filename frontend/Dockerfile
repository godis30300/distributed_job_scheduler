FROM python:3.11-slim

# Install dos2unix to handle line ending issues from Windows development
RUN apt-get update && apt-get install -y dos2unix && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Ensure all python files use Linux line endings
RUN find . -type f -name "*.py" -exec dos2unix {} +

RUN SECRET_KEY=dummy-build-key python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "scheduler_frontend.wsgi:application", "--bind", "0.0.0.0:8000"]
