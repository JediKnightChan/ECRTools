FROM python:3.8

WORKDIR /app

RUN pip install --no-cache-dir docker

COPY monitor/monitor.py .

ENV MONITOR_INTERVAL=5

CMD python monitor.py --interval ${MONITOR_INTERVAL} --logs_dir /logs
