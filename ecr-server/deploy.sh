docker build -t ecr-server .
docker tag ecr-server cr.yandex/crp110tk8f32a48oaeqo/ecr-server
docker push cr.yandex/crp110tk8f32a48oaeqo/ecr-server
