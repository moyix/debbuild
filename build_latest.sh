#!/bin/bash

DSC="$1"
SRC=$(awk '/^Source:/ { print $2 ; exit}' "$DSC")
VER=$(awk '/^Version:/ { print $2 ; exit}' "$DSC" | cut -d: -f2 | sed 's/-[^-]*$//')
sudo apt-get -y update
echo "Building $SRC version $VER"
cd $(dirname "$DSC")
rm -rf "${SRC}-${VER}"
TMPD=$(mktemp -d)
cd "$TMPD"
apt-get -y source "$SRC"
NEWDSC=$(ls *.dsc)
NEWSRC=$(awk '/^Source:/ { print $2 ; exit}' "$NEWDSC")
NEWVER=$(awk '/^Version:/ { print $2 ; exit}' "$NEWDSC" | cut -d: -f2 | sed 's/-[^-]*$//')
echo "Note: ${SRC}-${VER} => ${NEWSRC}-${NEWVER}"
cd $(dirname "$DSC")
sudo -E apt-get -y build-dep "$NEWSRC"
DEB_BUILD_OPTIONS="nodocs notest nocheck" timeout -v 6h bear --output "/fastdata/debian_allsrc/json/${NEWSRC}-${NEWVER}_compile_commands.json" -- apt-get -b source "$NEWSRC"
echo "Return value from dpkg-buildpackage: $?"
mv "${NEWSRC}-${NEWVER}" /data/research/debbuild_artifacts/latest
