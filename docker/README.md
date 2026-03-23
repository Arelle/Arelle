# Docker containers
Build and run an Arelle webserver with Docker. The EDGAR configuration includes the necessary dependencies
for the EDGAR plugins (render, validate, and transform) and EFM disclosure systems:
- Arelle
- EDGAR plugins
- xule plugin
```shell
# Clone and traverse into the Arelle repository
git clone --depth 1 https://github.com/Arelle/Arelle.git
cd Arelle

# Build and run the Arelle container
docker compose -f docker/docker-compose.yml up -d --build

# or build and run the Arelle container with the EDGAR plugin
docker compose -f docker/docker-compose.edgar.yml up -d --build
```
or in one line. The webserver will be available at [http://127.0.0.1:8080][local-arelle].
```shell
git clone --depth 1 https://github.com/Arelle/Arelle.git && cd Arelle && docker compose -f docker/docker-compose.yml up -d --build
```
[local-arelle]: http://127.0.0.1:8080

