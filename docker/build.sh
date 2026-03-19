# Move Docker compose file to Arelle directory
rm docker-compose.yml
cp ./docker/docker-compose.yml .

# Build and run docker container with docker compose
docker compose -f docker-compose.yml up -d --build
