if [ $# -eq 0 ]; then
  echo "No arguments supplied, rebuilding no cache to download server code"
  docker build -t ecr-server . --no-cache
else
  echo "At least 1 argument supplied, rebuilding with cache"
  docker build -t ecr-server .
fi

docker tag ecr-server cr.yandex/crp110tk8f32a48oaeqo/ecr-server
docker push cr.yandex/crp110tk8f32a48oaeqo/ecr-server
