FROM python:3.9

WORKDIR /app

COPY backend/requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py main.py
COPY backend/logic/ logic/
COPY backend/matchmaking_config.json matchmaking_config.json

CMD ["fastapi", "run", "main.py", "--port", "3000"]
