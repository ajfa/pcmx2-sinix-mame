#!/usr/bin/env python3
"""Find, and optionally patch, the console entry of /etc/termcap in an installed MC1325 image.

The patch switches the 97801 from the international key table (\\E[6u) to the German one
(\\E[7u), keeping the ASCII display set (\\E(B). SINIX then receives what MAME's natural
keyboard sends, so y/z and the symbols come out as typed.

usage: termcap.py <hd.img> [patch]
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hdfs import FFS

IMG = sys.argv[1]
PATCH = len(sys.argv) > 2 and sys.argv[2] == "patch"
ffs = FFS(IMG, 144)
ino = ffs.lookup("/etc/termcap")
_, data = ffs.read(ino)
k = data.find(b"console|:is=")
line = data[k:data.find(b"\n", k)]
print("termcap inode", ino, "console entry at file byte", k, ":", line)
old = b"\\E(B\\E[6u"
j = line.find(old)
if j < 0:
    print("no international key table in the console entry (already patched?)")
    sys.exit(0)
fb = k + j + len(old) - 2
blk, within = divmod(fb, ffs.BS)
off = ffs.OFF + ffs.block_addrs(ino)[blk] * ffs.FS + within
with open(IMG, "rb") as f:
    f.seek(off)
    cur = f.read(1)
print(f"byte at image offset {off:#x}: {cur!r}")
if PATCH:
    assert cur == b"6"
    with open(IMG, "r+b") as f:
        f.seek(off)
        f.write(b"7")
    print("patched to '7'")
