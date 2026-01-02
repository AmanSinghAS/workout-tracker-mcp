FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py
COPY src ./src
COPY allowed_emails.txt ./allowed_emails.txt
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY examples ./examples
COPY README.md ./README.md

EXPOSE 8080

CMD ["python", "server.py"]
