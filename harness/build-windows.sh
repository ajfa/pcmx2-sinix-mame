#!/bin/bash
# Native Windows build of the pcmx2 subtarget with MSYS2 (MINGW64 toolchain), run from an
# MSYS2 shell. Use a patched tree from build.sh copied to a Windows path; copying its
# build/generated directory along avoids regenerating it.
#   MAME_SRC   the patched tree (default: mame/ in this repository)
#   PYTHON     a Windows python.exe (the MSYS2 python does not work for the layout step)
set -u
export OS=Windows_NT
export MSYSTEM=MINGW64
export MINGW_PREFIX=/mingw64
export MINGW64=C:/msys64/mingw64
export PATH=/mingw64/bin:/usr/bin:$PATH
here=$(cd "$(dirname "$0")" && pwd)
cd "${MAME_SRC:-$here/../mame}" || exit 1
: "${PYTHON:?set PYTHON to a Windows python.exe}"
mingw32-make SUBTARGET=pcmx2 SOURCES=src/mame/siemens/pcmx2.cpp \
    PYTHON_EXECUTABLE="$PYTHON" MINGW64=C:/msys64/mingw64 PTR64=1 REGENIE=1 \
    TOOLCHAIN=C:/msys64/mingw64/bin/ NOWERROR=1 OPTIMIZE=2 SYMBOLS=0 TOOLS=0 -j"${JOBS:-6}"
rc=$?
[ $rc -eq 0 ] && strip pcmx2.exe && ls -l pcmx2.exe
exit $rc
