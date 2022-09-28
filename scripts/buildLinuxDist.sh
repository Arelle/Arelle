#!/bin/sh

set -xeu

DISTRO="${1:-linux}"
BUILD_DIR=build/exe.linux-x86_64-3.9
DIST_DIR=dist

rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

cp -p arelleGUI.pyw arelleGUI.py

python3 pygettext.py -v -o arelle/locale/messages.pot arelle/*.pyw arelle/*.py
python3 generateMessagesCatalog.py
python3 distro.py build_exe

cp -p arelle/scripts-unix/* "${BUILD_DIR}/"
cp -pR libs/linux/Tktable2.11 "${BUILD_DIR}/lib/"

SITE_PACKAGES=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
cp -pR "${SITE_PACKAGES}/mpl_toolkits" "${BUILD_DIR}/lib/"
cp -pR "${SITE_PACKAGES}/numpy.libs" "${BUILD_DIR}/lib/"
cp -pR "${SITE_PACKAGES}/Pillow.libs" "${BUILD_DIR}/lib/"

cp -p "$(find /lib /usr -name libexslt.so.0)" "${BUILD_DIR}/"
cp -p "$(find /lib /usr -name libxml2.so)" "${BUILD_DIR}/"
cp -p "$(find /lib /usr -name libxml2.so.2)" "${BUILD_DIR}/"
cp -p "$(find /lib /usr -name libxslt.so.1)" "${BUILD_DIR}/"
cp -p "$(find /lib /usr -name libz.so.1)" "${BUILD_DIR}/"

VERSION=$(python3 -c "import arelle._version; print(arelle._version.version)")

tar -czf "${DIST_DIR}/arelle-${DISTRO}-${VERSION}.tgz" --directory "${BUILD_DIR}" .
