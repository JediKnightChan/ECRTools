sudo apt-get update
sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable"
apt-cache policy docker-ce
sudo apt install docker-ce
sudo systemctl status docker

sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker

cat key.json | docker login --username json_key --password-stdin cr.yandex