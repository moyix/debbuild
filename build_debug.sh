#!/bin/bash

DSC="$1"
SRC=$(awk '/^Source:/ { print $2 ; exit}' "$DSC")
VER=$(awk '/^Version:/ { print $2 ; exit}' "$DSC" | cut -d: -f2 | sed 's/-[^-]*$//')
sudo apt-get -y update
echo "Building $SRC"
cd $(dirname "$DSC")
rm -rf "${SRC}-${VER}"
dpkg-source -x "$DSC"
cd "${SRC}-${VER}"
sudo -E apt-get -y build-dep "$SRC"
DEB_BUILD_OPTIONS="nodocs notest nocheck" timeout -v 6h strace -f dpkg-buildpackage -rfakeroot
