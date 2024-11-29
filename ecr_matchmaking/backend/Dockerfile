FROM python:3.9

WORKDIR /app

COPY backend/requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py main.py

CMD ["fastapi", "run", "main.py", "--port", "3000"]
