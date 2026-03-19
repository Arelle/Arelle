# Move Docker compose file to Arelle directory
rm docker-compose.edgar.yml
cp ./docker/EDGAR/docker-compose.edgar.yml .

# Build and run docker container with docker compose
docker compose -f docker-compose.edgar.yml up -d --build
