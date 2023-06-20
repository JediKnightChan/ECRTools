docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)
docker rmi -f $(docker images -aq)

docker pull cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest
docker run --restart always -p 7777:7777/udp -d cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest
