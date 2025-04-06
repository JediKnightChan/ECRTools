FROM python:3.8

WORKDIR /app

# Separately clone requirements not to reinstall them when other files change
COPY backend/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY backend/ .

# 7777 is for only 1 game instance, e.g. for 10 need to expose 7777-7786
EXPOSE 7777/tcp
EXPOSE 7777/udp

CMD uvicorn main:app --host 127.0.0.1 --port 3000 --workers 1