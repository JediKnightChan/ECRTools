FROM python:3.8

WORKDIR /ecr-server

RUN apt-get install unzip -y
RUN wget https://ecr-service.website.yandexcloud.net/dist/builds/LinuxServer.zip
RUN unzip LinuxServer.zip
RUN rm -f LinuxServer.zip

RUN chmod 755 LinuxServer/ECRServer.sh
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer || true
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer-Shipping || true

RUN useradd -ms /bin/bash ecr-server
RUN chown -R ecr-server:ecr-server LinuxServer/

# Separately clone requirements not to reinstall them when other files change
COPY backend/requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Install time for monitoring game server
RUN apt-get install coreutils -y

COPY backend/ .

RUN chown ecr-server:ecr-server .

USER ecr-server

# 7777 is for only 1 game instance, e.g. for 10 need to expose 7777-7786
EXPOSE 7777/tcp
EXPOSE 7777/udp

CMD uvicorn main:app --host 127.0.0.1 --port 3000
