# Arelle Docker container with EDGAR plugin
This script builds an Arelle docker container with the necessary dependancies for the EDGAR plugin and EFM validation and starts the webserver at [http://127.0.0.1:8080][local-arelle].
- Arelle
- EDGAR plugin
- xule plugin

```shell
# Clone the Arelle repository
git clone --depth 1 https://github.com/Arelle/Arelle.git

# Make the script executable
chmod +x Arelle/docker/EDGAR/build_EDGAR.sh

# Run the build script
Arelle/docker/EDGAR/build_EDGAR.sh
```
or in one line
```shell
git clone --depth 1 https://github.com/Arelle/Arelle.git && chmod +x Arelle/docker/EDGAR/build_EDGAR.sh && Arelle/docker/EDGAR/build_EDGAR.sh
```
[local-arelle]: http://127.0.0.1:8080
