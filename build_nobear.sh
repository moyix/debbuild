#!/bin/bash

DSC="$1"
SRC=$(awk '/^Source:/ { print $2 ; exit}' "$DSC")
VER=$(awk '/^Version:/ { print $2 ; exit}' "$DSC" | cut -d: -f2 | sed 's/-[^-]*$//')
echo "Building $SRC"
dpkg-source -x "$DSC"
cd $(dirname "$DSC")
rm -rf "${SRC}-${VER}"
dpkg-source -x "$DSC"
cd "${SRC}-${VER}"
sudo apt-get -y build-dep "$SRC"
DEB_BUILD_OPTIONS="nodocs notest nocheck" timeout 30m dpkg-buildpackage -rfakeroot
