#!/bin/sh

set -xeu

DISTRO="${1:-linux}"
BUILD_DIR=build
DIST_DIR=dist
# setuptools_scm detects the current version based on the distance from latest
# git tag and if there are uncommitted changes. Capture version prior to
# localization build scripts which will create uncommitted changes.
VERSION=$(python3 -W ignore distro.py --version)

rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

cp -p arelleGUI.pyw arelleGUI.py

python3 pygettext.py -v -o arelle/locale/messages.pot arelle/*.pyw arelle/*.py
python3 generateMessagesCatalog.py
SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION} python3 distro.py build_exe

DISTRO_DIR=$(find build -name "exe.linux-*")

cp -p arelle/scripts-unix/* "${DISTRO_DIR}/"
cp -pR libs/linux/Tktable2.11 "${DISTRO_DIR}/lib/"

SITE_PACKAGES=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
cp -pR "${SITE_PACKAGES}/mpl_toolkits" "${DISTRO_DIR}/lib/"
cp -pR "${SITE_PACKAGES}/numpy.libs" "${DISTRO_DIR}/lib/"
cp -pR "${SITE_PACKAGES}/Pillow.libs" "${DISTRO_DIR}/lib/"

cp -p "$(find /lib /usr -name libexslt.so.0)" "${DISTRO_DIR}/"
cp -p "$(find /lib /usr -name libxml2.so)" "${DISTRO_DIR}/"
cp -p "$(find /lib /usr -name libxml2.so.2)" "${DISTRO_DIR}/"
cp -p "$(find /lib /usr -name libxslt.so.1)" "${DISTRO_DIR}/"
cp -p "$(find /lib /usr -name libz.so.1)" "${DISTRO_DIR}/"

VERSION=$(python3 -c "import arelle._version; print(arelle._version.version)")

tar -czf "${DIST_DIR}/arelle-${DISTRO}-${VERSION}.tgz" --directory "${DISTRO_DIR}" .
