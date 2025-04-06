FROM python:3.8

WORKDIR /ecr-server

# Install dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    unzip \
    time

RUN wget https://ecr-service.website.yandexcloud.net/dist/builds/LinuxServer.zip
RUN unzip LinuxServer.zip
RUN rm -f LinuxServer.zip

RUN chmod 755 LinuxServer/ECRServer.sh
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer || true
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer-Shipping || true

RUN useradd -ms /bin/bash ecr-server
RUN chown -R ecr-server:ecr-server LinuxServer/

# Copying content of game server (launch script)
COPY gameserver/ .
RUN chown ecr-server:ecr-server .

# Creating a Logs dir before it's mounted to set ownership to us
RUN mkdir -p LinuxServer/ECR/Saved/Logs && \
    chown -R ecr-server:ecr-server /ecr-server/LinuxServer/ECR/Saved

USER ecr-server

# 7777 is for only game instance with number 0, e.g. for game instance number 10 need to expose 7786
EXPOSE 7777/tcp
EXPOSE 7777/udp

CMD python3 launch_server.py
