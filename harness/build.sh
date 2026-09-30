#!/bin/bash
# Clone David Rand's storager-lle branch of MAME at the commit the patches were made
# against, apply them in order and build the pcmx2 subtarget.
#   MAME_SRC   where the tree goes (default: mame/ in this repository)
#   JOBS       make jobs (default 2: luaengine.cpp needs a lot of memory per job)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
src=${MAME_SRC:-$here/../mame}
base=0147a62a34d
if [ ! -d "$src/.git" ]; then
    git clone --branch storager-lle https://github.com/davidlrand/mame "$src"
fi
cd "$src"
git checkout -q "$base"
for p in "$here"/../patches/*.patch; do
    echo "applying $(basename "$p")"
    git apply "$p"
done
make SUBTARGET=pcmx2 SOURCES=src/mame/siemens/pcmx2.cpp -j"${JOBS:-2}"
ls -l pcmx2
