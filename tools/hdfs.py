#!/usr/bin/env python3
"""Read files from an installed SINIX V2.0 MC1325 disk image.

The root file system is a 4.2BSD FFS variant (magic 0x90545, 4 KB blocks, 1 KB fragments).
On the MC1325 the root (wn1) starts at 512-byte sector 144 and /usr (wn3) at 28800.

usage: hdfs.py <hd.img> <start sector> [path ...]
"""
import sys, struct


class FFS:
    def __init__(self, image, sector):
        self.img = open(image, "rb")
        self.OFF = sector * 512
        sb = self.rd(8192, 2048)
        names = ["link", "rlink", "sblkno", "cblkno", "iblkno", "dblkno", "cgoffset", "cgmask", "time",
                 "size", "dsize", "ncg", "bsize", "fsize", "frag"]
        fs = dict(zip(names, struct.unpack_from("<15i", sb, 0)))
        n2 = ["csaddr", "cssize", "cgsize", "ntrak", "nsect", "spc", "ncyl", "cpg", "ipg", "fpg"]
        fs.update(zip(n2, struct.unpack_from("<10i", sb, 33 * 4 + 5 * 4)))
        self.magic = struct.unpack_from("<i", sb, 1372)[0]
        self.fs = fs
        self.FS, self.BS = fs["fsize"], fs["bsize"]

    def rd(self, off, n):
        self.img.seek(self.OFF + off)
        return self.img.read(n)

    def inode(self, ino):
        fs = self.fs
        c = ino // fs["ipg"]
        base = fs["fpg"] * c + fs["cgoffset"] * (c & ~fs["cgmask"])
        per_frag = self.FS // 128
        frag = base + fs["iblkno"] + (ino % fs["ipg"]) // per_frag
        d = self.rd(frag * self.FS + ((ino % fs["ipg"]) % per_frag) * 128, 128)
        mode, = struct.unpack_from("<H", d, 0)
        size, = struct.unpack_from("<I", d, 8)
        db = struct.unpack_from("<12I", d, 40)
        ib = struct.unpack_from("<3I", d, 88)
        return mode, size, db, ib

    def block_addrs(self, ino):
        mode, size, db, ib = self.inode(ino)
        addrs = list(db)
        if ib[0]:
            addrs += list(struct.unpack("<%dI" % (self.BS // 4), self.rd(ib[0] * self.FS, self.BS)))
        return addrs

    def read(self, ino):
        mode, size, _, _ = self.inode(ino)
        out = b""
        for a in self.block_addrs(ino):
            if len(out) >= size:
                break
            n = min(self.BS, size - len(out))
            out += self.rd(a * self.FS, n) if a else b"\0" * n
        return mode, out[:size]

    def lookup(self, path):
        ino = 2
        for part in [p for p in path.split("/") if p]:
            mode, d = self.read(ino)
            found = None
            for k in range(0, len(d), 16):
                e, = struct.unpack_from("<H", d, k)
                nm = d[k + 2:k + 16].split(b"\0")[0].decode("latin1")
                if e and nm == part:
                    found = e
            if not found:
                return None
            ino = found
        return ino


if __name__ == "__main__":
    ffs = FFS(sys.argv[1], int(sys.argv[2]))
    print("magic", hex(ffs.magic), "bsize", ffs.BS, "fsize", ffs.FS)
    for p in sys.argv[3:]:
        ino = ffs.lookup(p)
        print("=====", p, "inode", ino)
        if ino:
            print(ffs.read(ino)[1].decode("latin1"))
