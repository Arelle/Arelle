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

## Build
```shell
docker build -t arelle-webserver -f docker/Dockerfile .

# With the EDGAR plugins
docker build --build-arg INCLUDE_EDGAR="true" --build-arg EXTRA_PIP="-r requirements-plugins.txt" -t arelle-edgar-webserver -f docker/Dockerfile .
```

## Run
```shell
# To run the command line
docker run arelle-webserver python arelleCmdLine.py --help
# To run the webserver
docker run --name arelle-webserver -p 8080:8080 arelle-webserver /start.sh

# With the EDGAR plugins
docker run arelle-edgar-webserver python arelleCmdLine.py --help
docker run --name arelle-edgar-webserver -p 8080:8080 arelle-edgar-webserver /start.sh
```

[local-arelle]: http://127.0.0.1:8080

