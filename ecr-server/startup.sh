# chmod +x startup.sh
# crontab -e
# @reboot /home/pchela/startup.sh >> /home/pchela/startup_log.txt

docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)

LATEST_IMAGE_HASH=$(curl -s https://ecr-service.website.yandexcloud.net/api/ecr/server_data/latest_server_image_hash.txt)
IMAGE_HASH_RAW=$(docker inspect --format='{{index .RepoDigests 0}}' cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest)
IMAGE_HASH="${IMAGE_HASH_RAW#*:}"

date

if [[ "$IMAGE_HASH" == "$LATEST_IMAGE_HASH" ]]; then
  echo "$IMAGE_HASH is latest hash, skipping updating"
else
  # Small disk space servers, remove image before re downloading
  echo "New hash is available, $LATEST_IMAGE_HASH, reinstalling"
  docker rmi -f $(docker images -aq)
  docker pull cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest
fi

WANTED_REGION=""
if test -f "/home/pchela/region.txt"; then
  WANTED_REGION=$(cat region.txt)
  echo "Wanted region set, $WANTED_REGION"
else
  echo "Wanted region not set, will use API to determine it"
fi

# shellcheck disable=SC2089
COMMAND="docker run --restart always -p 7777:7777/udp -e REGION=\"$WANTED_REGION\" -d cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest"
eval "$COMMAND"
