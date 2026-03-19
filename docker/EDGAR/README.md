# Arelle Docker container with EDGAR plugin
This script builds an Arelle docker container with the necessary dependancies for the EDGAR plugin and EFM validation and starts the webserver at [http://127.0.0.1:8080][local-arelle].
- Arelle
- EDGAR plugin
- xule plugin

```shell
# Clone and traverse into the Arelle repository
git clone --depth 1 https://github.com/Arelle/Arelle.git
cd Arelle

# Build and run the Arelle container
docker compose -f docker/EDGAR/docker-compose.edgar.yml up -d --build
```
or in one line
```shell
git clone --depth 1 https://github.com/Arelle/Arelle.git && cd Arelle && docker compose -f docker/EDGAR/docker-compose.edgar.yml up -d --build
```
[local-arelle]: http://127.0.0.1:8080
