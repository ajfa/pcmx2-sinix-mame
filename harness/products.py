#!/usr/bin/env python3
"""Install SINIX V2.0 software products on an installed pcmx2 disk, headless.

Boots WORK/<label>/hd.img (put an installed disk there first), logs in as admin,
goes to Systemverwaltung -> Installation von Softwareprodukten, and for each product
inserts its first floppy, answers "j", and feeds every floppy that /etc/waitfl asks for.
Floppy labels are read from the VOL1 record of the IMD files (set1 wins over set2).

usage: products.py <label> <first floppy label> [...]   e.g. products.py s1 CES1 OBG1 INFDE1 PASXT1
       products.py <label> root <file>                   log in as root and run one shell
                                                         command per line (end with /etc/haltsys)

environment: PCMX2, ROMS, FLOPPIES, WORK as for install.py; MAMEARGS adds MAME options
"""
import os, re, subprocess, sys, time, threading, shutil, glob

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
PCMX2 = os.path.abspath(os.environ.get("PCMX2", os.path.join(TOP, "mame", "pcmx2")))
ROMS = os.path.abspath(os.environ.get("ROMS", os.path.join(TOP, "roms")))
FLOPPIES = os.path.abspath(os.environ.get("FLOPPIES", os.path.join(TOP, "floppies")))
RUN = os.path.abspath(os.environ.get("WORK", os.path.join(TOP, "work")))
LABEL = sys.argv[1]
PRODUCTS = sys.argv[2:]
WORK = os.path.join(RUN, LABEL)
HD = os.path.join(WORK, "hd.img")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][0-9A-Za-z]")
t0 = time.time()

FLOPS = {}
for s in ("set2", "set1"):
    for b in sorted(glob.glob(os.path.join(FLOPPIES, s, "*.imd"))):
        d = open(b, "rb").read(16384)
        i = d.find(b"VOL1")
        if i >= 0:
            name = d[i + 4:i + 10].split(b"\0")[0].strip().decode("latin1")
            FLOPS[name] = b

def say(s):
    line = f"[{time.time() - t0:7.0f}s] {s}"
    print(line, flush=True)
    with open(os.path.join(WORK, "harness.log"), "a") as f:
        f.write(line + "\n")

# The OBG set in Tenox's archive is a 1986 copy whose VOL1 labels read "OBG-1".."OBG-3",
# while its install script checks for OBG1..OBG3 (flchk/waitfl): relabel the scratch copy.
for n in ("OBG-1", "OBG-2", "OBG-3"):
    if n in FLOPS:
        FLOPS[n.replace("-", "")] = FLOPS[n]

def scratch(label):
    dst = os.path.join(WORK, label + ".imd")
    data = open(FLOPS[label], "rb").read()
    for n in ("OBG-1", "OBG-2", "OBG-3"):
        data = data.replace(b"VOL1" + n.encode() + b" ", b"VOL1" + n.replace("-", "").encode() + b"  ")
    with open(dst, "wb") as f:
        f.write(data)
    os.chmod(dst, 0o644)
    return dst

class Machine:
    def __init__(self, secs):
        self.con = os.path.join(WORK, "con.txt")
        self.ctl = os.path.join(WORK, "flctl")
        open(self.ctl, "w").close()
        cmd = [PCMX2, "pcmx2", "-rompath", ROMS,
               "-video", "none", "-sound", "none", "-verbose", "-nothrottle", "-seconds_to_run", secs,
               "-hard1", HD, "-slot3:serad:port0", "pty",
               "-autoboot_script", os.path.join(HERE, "floppies.lua")] + os.environ.get("MAMEARGS", "").split()
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", FLCTL=self.ctl)
        self.p = subprocess.Popen(cmd, cwd=WORK, stdout=open(os.path.join(WORK, "mame.out"), "wb"),
                                  stderr=subprocess.STDOUT, env=env)
        # MAME's own pty, from the tty-index of its /dev/ptmx descriptor: a diff of /dev/pts
        # picks up ptys that other programs open at the same time
        slave = None
        for _ in range(120):
            time.sleep(1)
            fdd = f"/proc/{self.p.pid}/fd"
            try:
                for fd in os.listdir(fdd):
                    if os.readlink(os.path.join(fdd, fd)) == "/dev/ptmx":
                        for line in open(f"/proc/{self.p.pid}/fdinfo/{fd}"):
                            if line.startswith("tty-index:"):
                                slave = "/dev/pts/" + line.split()[1]
            except OSError:
                pass
            if slave or self.p.poll() is not None:
                break
        if not slave:
            say("MAME opened no pty")
            sys.exit(1)
        self.fd = os.open(slave, os.O_RDWR | os.O_NOCTTY)
        self.raw = bytearray()
        self.lock = threading.Lock()
        self.pos = {}
        threading.Thread(target=self.reader, daemon=True).start()

    def reader(self):
        out = open(self.con, "wb")
        while True:
            try:
                d = os.read(self.fd, 4096)
            except OSError:
                break
            if d:
                out.write(d); out.flush()
                with self.lock:
                    self.raw.extend(d)
            else:
                time.sleep(0.05)

    def text(self):
        with self.lock:
            return ANSI.sub("", self.raw.decode("latin1"))

    def find(self, pattern):
        t = self.text()
        m = re.compile(pattern).search(t, self.pos.get(pattern, 0))
        if m:
            self.pos[pattern] = m.end()
        return m

    def skip(self, *patterns):
        n = len(self.text())
        for p in patterns:
            self.pos[p] = n

    def send(self, s, why, delay=3):
        time.sleep(delay)
        os.write(self.fd, s.encode())
        say(f"sent {s!r} ({why})")

    def floppy(self, what):
        with open(self.ctl, "w") as f:
            f.write(what + "\n")
        say(f"floppy <- {what}")

    def alive(self):
        return self.p.poll() is None

    def stop(self):
        if self.alive():
            self.p.terminate()
            try:
                self.p.wait(30)
            except subprocess.TimeoutExpired:
                self.p.kill()

    def wait(self, pattern, secs, fail=(r"panic:",)):
        end = time.time() + secs
        while time.time() < end and self.alive():
            time.sleep(0.5)
            m = self.find(pattern)
            if m:
                return m
            for f in fail:
                if self.find(f):
                    say(f"stop condition {f!r}")
                    return None
        say(f"timeout waiting for {pattern!r}")
        return None

def login(m, user, password):
    pats = (r"Kennwort:", r"Bitte waehlen|# ", r"Falsche Angaben|Benutzerkennung:")
    for attempt in (1, 2, 3):
        time.sleep(15)
        m.skip(*pats)
        m.send(user + "\r", f"login {user} (attempt {attempt})")
        end = time.time() + 120
        while time.time() < end and m.alive():
            time.sleep(0.3)
            if m.find(pats[0]):
                time.sleep(0.5)
                os.write(m.fd, (password + "\r").encode())
                say(f"sent password for {user}")
            if m.find(pats[1]):
                say(f"logged in as {user}")
                return True
            if m.find(pats[2]):
                say("login did not go through")
                break
    return False

def install(m, first, enter_menu):
    m.skip(r"Installation jetzt beginnen")
    if enter_menu:
        m.skip(r"Bitte waehlen")
        m.send("s\r", "Systemverwaltung")
        if not m.wait(r"Installation von Softwareprodukten", 120):
            return False
        m.wait(r"Bitte waehlen", 60)
    m.send("i\r", "Installation von Softwareprodukten")
    if not m.wait(r"Installation jetzt beginnen", 120):
        return False
    m.floppy(scratch(first))
    time.sleep(8)
    m.send("j\r", f"{first} inserted, begin")
    end = time.time() + 7200
    while time.time() < end and m.alive():
        time.sleep(1)
        r = m.find(r"Diskette (\S+) einlegen")
        if r:
            want = r.group(1)
            if want in FLOPS:
                m.floppy(scratch(want))
                time.sleep(8)
                m.send("j\r", f"{want} inserted")
            else:
                say(f"asks for unknown floppy {want!r}")
                return False
        if m.find(r"Installation erfolgreich abgeschlossen"):
            say(f"{first}: installation finished OK")
            m.floppy("unload")
            return True
        for pat in (r"konnte nicht erfolgreich", r"nicht gefunden", r"stimmen nicht ueberein", r"panic:",
                    r"No space|file system full"):
            if m.find(pat):
                say(f"{first}: stop condition {pat!r}")
                return False
    return False

def root_session(m, cmds):
    if not login(m, "root", "siemens"):
        return False
    for c in cmds:
        m.skip(r"\n# ")
        m.send(c + "\r", "root command", delay=2)
        if c.startswith("/etc/haltsys"):
            return bool(m.wait(r"Halt the processor", 300))
        if not m.wait(r"\n# ", 900):
            return False
    return True

if __name__ == "__main__":
    say(f"label {LABEL}, products {PRODUCTS}, floppies known: {sorted(FLOPS)}")
    m = Machine("40000")
    ok = True
    while m.alive():
        time.sleep(1)
        if m.find(r"sasiopen: no label SINIX found\s*\n:"):
            m.send("sa(1,0)sinix\r", "loader prompt")
        if m.find(r"eingeben \[jj\]"):
            m.send(time.strftime("86%m%d%H%M") + "\r", "date, year 1986")
        if m.find(r"Benutzerkennung:"):
            break
    if PRODUCTS and PRODUCTS[0] == "root":
        # root <file with one shell command per line>; end it with /etc/haltsys for a clean disk
        ok = root_session(m, [l.rstrip("\n") for l in open(PRODUCTS[1]) if l.strip()])
    elif login(m, "admin", "siemens"):
        for n, p in enumerate(PRODUCTS):
            if not install(m, p, n == 0):
                ok = False
                break
            time.sleep(10)
    time.sleep(10)
    say("done, ok=" + str(ok))
    m.stop()
