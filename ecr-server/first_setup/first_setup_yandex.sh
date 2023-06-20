sudo apt-get update
sudo apt-get install docker docker.io
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker

cat key.json | docker login --username json_key --password-stdin cr.yandex