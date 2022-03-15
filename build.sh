#!/bin/bash -x

NAME="$1"
sudo apt-get -y update
echo "Building $NAME"
python3 /scripts/list_srcgz.py check "$NAME" || exit 1
cd /build/
eval $(python3 /scripts/list_srcgz.py env "$NAME")
[ -f "$DSC" ] || python3 /scripts/list_srcgz.py urls "$NAME" | wget -i -
[ -f "$DSC" ] || exit 1
[ -d "${PKG}-${VER}" ] && rm -rf "${PKG}-${VER}"
dpkg-source -x "$DSC"
# Get build deps
mk-build-deps -ir -t "apt-get -y -o Debug::pkgProblemResolver=yes --no-install-recommends" -s "sudo -E" "${PKG}-${VER}"/debian/control || \
    sudo -E apt-get -y build-dep "$PKG" || exit 1
# Remove leftover cruft so that dpkg-buildpackage doesn't complain
rm -f "${PKG}"-build-deps_*.buildinfo "${PKG}"-build-deps_*.changes
PKGDIR=/build/"${PKG}-${VER}"
# Apply fixups, if any
if [ -f /fastdata/fixups/${PKG}.sh ]; then
    echo "Applying fixups for ${PKG}"
    bash /fastdata/fixups/${PKG}.sh "${PKGDIR}"
fi
# Build
cd /build/"${PKG}-${VER}" || exit 1
DEB_BUILD_OPTIONS="notest nocheck" timeout -v 6h bear --output "/fastdata/debian_allsrc/json/${PKG}-${VER}_compile_commands.json" -- dpkg-buildpackage -us -uc
echo "Return value from dpkg-buildpackage: $?"
cd /build/
#mv "${PKG}-${VER}" /data/research/debbuild_artifacts/
#python3 /scripts/list_srcgz.py clean "$NAME" | bash
