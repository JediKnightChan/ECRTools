# chmod +x startup.sh
# crontab -e
# @reboot /home/eternalcrusaderesurrection/startup.sh > /home/eternalcrusaderesurrection/startup_log.txt

docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)

LATEST_IMAGE_HASH_RAW=$(docker manifest inspect cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest -v | jq -r .Descriptor.digest)
IMAGE_HASH_RAW=$(docker inspect --format='{{index .RepoDigests 0}}' cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest)
IMAGE_HASH_RAW="${IMAGE_HASH_RAW#*@}"

date

HASHES_EQUAL_RESULT=$(/usr/bin/python3 /home/eternalcrusaderesurrection/string_comparer.py "$IMAGE_HASH_RAW" "$LATEST_IMAGE_HASH_RAW")

if [ $? -eq 0 ]; then
  echo "$IMAGE_HASH_RAW is latest hash, skipping updating"
else
  # Small disk space servers, remove image before re downloading
  echo "Output of comparer is $HASHES_EQUAL_RESULT: new hash is available, $LATEST_IMAGE_HASH_RAW, reinstalling (old one is $IMAGE_HASH_RAW)"
  docker rmi -f $(docker images -aq)
  docker pull cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest
fi


WANTED_REGION=""
if test -f "/home/eternalcrusaderesurrection/region.txt"; then
  WANTED_REGION=$(cat region.txt)
  echo "Wanted region set, $WANTED_REGION"
else
  echo "Wanted region not set, will use API to determine it"
fi

# shellcheck disable=SC2089
COMMAND="docker run --restart always -p 7777:7777/udp -e REGION=\"$WANTED_REGION\" -d cr.yandex/crp110tk8f32a48oaeqo/ecr-server:latest"
eval "$COMMAND"
