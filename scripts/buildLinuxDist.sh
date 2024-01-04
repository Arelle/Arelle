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

for pythonLib in "mpl_toolkits" "numpy.libs" "pillow.libs"; do
  pythonLibFullPath=$(find "${SITE_PACKAGES}" -maxdepth 1 -type d -iname "${pythonLib}")
  cp -pR "${pythonLibFullPath}" "${DISTRO_DIR}/lib/"
done

for lib in "libexslt.so.0" "libxml2.so" "libxml2.so.2" "libxslt.so.1" "libz.so.1"; do
  libFullPath=$(find /lib /usr -name ${lib})
  cp -p "${libFullPath}" "${DISTRO_DIR}/"
done

VERSION=$(python3 -c "import arelle._version; print(arelle._version.version)")

tar -czf "${DIST_DIR}/arelle-${DISTRO}-${VERSION}.tgz" --directory "${DISTRO_DIR}" .
