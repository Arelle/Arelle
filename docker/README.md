# Arelle Docker container
This script builds an Arelle docker container and starts the webserver at [http://127.0.0.1:8080][local-arelle].
```shell
# Clone the Arelle repository
git clone --depth 1 https://github.com/Arelle/Arelle.git

# Make the script executable
chmod +x Arelle/docker/build.sh

# Run the build script
Arelle/docker/build.sh
```
or in one line
```shell
git clone --depth 1 https://github.com/Arelle/Arelle.git && chmod +x Arelle/docker/build.sh && Arelle/docker/build.sh
```
[local-arelle]: http://127.0.0.1:8080
