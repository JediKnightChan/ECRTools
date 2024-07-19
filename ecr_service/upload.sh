# Upload ecr-service index.json and api folder to S3

aws s3 cp api/ s3://ecr-service/api --recursive
aws s3 cp index.json s3://ecr-service/index.json
