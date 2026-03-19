# Arelle Docker container
This script builds an Arelle docker container and starts the webserver at [http://127.0.0.1:8080][local-arelle].
```shell
# Clone and traverse into the Arelle repository
git clone --depth 1 https://github.com/Arelle/Arelle.git
cd Arelle

# Build and run the Arelle container
docker compose -f docker/docker-compose.yml up -d --build
```
or in one line
```shell
git clone --depth 1 https://github.com/Arelle/Arelle.git && cd Arelle && docker compose -f docker/docker-compose.yml up -d --build
```
[local-arelle]: http://127.0.0.1:8080
