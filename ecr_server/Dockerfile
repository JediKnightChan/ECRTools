FROM python:3.8

WORKDIR /ecr-server

RUN apt-get install unzip -y
RUN wget https://ecr-service.website.yandexcloud.net/dist/builds/LinuxServer.zip
RUN unzip LinuxServer.zip
RUN rm -f LinuxServer.zip

RUN chmod 755 LinuxServer/ECRServer.sh
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer || true
RUN chmod 755 LinuxServer/ECR/Binaries/Linux/ECRServer-Shipping || true

# Separately clone requirements not to reinstall them when other files change
COPY docker/requirements.txt .
RUN pip install -r requirements.txt

COPY docker/ .

RUN useradd -ms /bin/bash ecr-server
RUN chown -R ecr-server:ecr-server .

USER ecr-server

EXPOSE 7777/tcp
EXPOSE 7777/udp

CMD python3 launch_server.py
