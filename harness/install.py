#!/usr/bin/env python3
"""Full SINIX V2.0 installation on pcmx2, headless, in two MAME runs.

Phase A boots SINIX0 on a blank disk: answers the first-install question and the disk
type, lets the installer format the disk and copy the minimal system, and stops at
"Halt the Processor" (the installer's "switch off and remove the floppy").
Phase B boots that disk with no floppy; every "Diskette SINIXn einlegen" prompt gets a
scratch copy of that diskette hot-loaded through floppies.lua, then "j".

At the login prompt it logs in as mgast (menu guest, no password) and waits for the menu.
Linux only (the console is a pty).

usage: install.py <label> [set1|set2] [secsA] [secsB]
       install.py <label> verify [user [password]]
                              boot the installed disk of <label> and log in
                              (factory passwords: root and admin 'siemens'; user '-' leaves
                              the machine up at the login prompt)

environment: PCMX2    the pcmx2 binary (default mame/pcmx2 in the repository)
             ROMS     ROM directory (default roms/)
             FLOPPIES directory holding set1/ and set2/ with Tenox's IMD files (default floppies/)
             WORK     work directory (default work/); the disk ends up in WORK/<label>/hd.img
"""
import os, re, subprocess, sys, time, threading, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
PCMX2 = os.path.abspath(os.environ.get("PCMX2", os.path.join(TOP, "mame", "pcmx2")))
ROMS = os.path.abspath(os.environ.get("ROMS", os.path.join(TOP, "roms")))
FLOPPIES = os.path.abspath(os.environ.get("FLOPPIES", os.path.join(TOP, "floppies")))
RUN = os.path.abspath(os.environ.get("WORK", os.path.join(TOP, "work")))
LABEL = sys.argv[1] if len(sys.argv) > 1 else "inst"
VERIFY = len(sys.argv) > 2 and sys.argv[2] == "verify"
SET = sys.argv[2] if len(sys.argv) > 2 and not VERIFY else "set1"
V_USER = sys.argv[3] if VERIFY and len(sys.argv) > 3 else "mgast"
V_PASS = sys.argv[4] if VERIFY and len(sys.argv) > 4 else None
SECS_A = sys.argv[3] if len(sys.argv) > 3 else "4000"
SECS_B = sys.argv[4] if len(sys.argv) > 4 else "40000"
DISKS = {"set1": {f"SINIX{i}": f"mx2-{i + 1:03d}.imd" for i in range(8)},
         "set2": {f"SINIX{i}": f"mx2-a{i + 3:02d}.imd" for i in range(8)}}[SET]
IMD = os.path.join(FLOPPIES, SET)
WORK = os.path.join(RUN, LABEL)
os.makedirs(WORK, exist_ok=True)
HD = os.path.join(WORK, "hd.img")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][0-9A-Za-z]")
t0 = time.time()

def say(s):
    line = f"[{time.time() - t0:7.0f}s] {s}"
    print(line, flush=True)
    with open(os.path.join(WORK, "harness.log"), "a") as f:
        f.write(line + "\n")

def scratch(label):
    dst = os.path.join(WORK, label + ".imd")
    shutil.copyfile(os.path.join(IMD, DISKS[label]), dst)
    os.chmod(dst, 0o644)
    return dst

class Machine:
    def __init__(self, phase, secs, floppy):
        self.phase = phase
        self.con = os.path.join(WORK, f"con-{phase}.txt")
        self.ctl = os.path.join(WORK, "flctl")
        open(self.ctl, "w").close()
        cmd = [PCMX2, "pcmx2", "-rompath", ROMS,
               "-video", "none", "-sound", "none", "-verbose", "-nothrottle", "-seconds_to_run", secs,
               "-hard1", HD, "-slot3:serad:port0", "pty",
               "-autoboot_script", os.path.join(HERE, "floppies.lua")]
        if floppy:
            cmd += ["-flop", floppy]
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", FLCTL=self.ctl)
        self.p = subprocess.Popen(cmd, cwd=WORK, stdout=open(os.path.join(WORK, f"mame-{phase}.out"), "wb"),
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
            say(f"{phase}: MAME opened no pty")
            sys.exit(1)
        say(f"{phase}: MAME pid {self.p.pid}, console {slave}, floppy {floppy}")
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
        # next unconsumed match of pattern, or None
        t = self.text()
        m = re.compile(pattern).search(t, self.pos.get(pattern, 0))
        if m:
            self.pos[pattern] = m.end()
        return m

    def skip(self, *patterns):
        # mark everything on screen so far as consumed for these patterns
        n = len(self.text())
        for p in patterns:
            self.pos[p] = n

    def send(self, s, why):
        time.sleep(3)
        os.write(self.fd, s.encode())
        say(f"{self.phase}: sent {s!r} ({why})")

    def floppy(self, what):
        with open(self.ctl, "w") as f:
            f.write(what + "\n")
        say(f"{self.phase}: floppy <- {what}")

    def alive(self):
        return self.p.poll() is None

    def stop(self):
        if self.alive():
            self.p.terminate()
            try:
                self.p.wait(30)
            except subprocess.TimeoutExpired:
                self.p.kill()

def phase_a():
    # blank Micropolis MC1325: 1024 cylinders, 8 heads, 18 sectors of 512 bytes
    with open(HD, "wb") as f:
        f.truncate(1024 * 8 * 18 * 512)
    m = Machine("A", SECS_A, scratch("SINIX0"))
    rules = [(r"sasiopen: no label SINIX found\s*\n:", "sa(22,0)sinix\r", "boot prompt"),
             (r"Antworten Sie mit", "j\r", "first installation"),
             (r"Plattentyp", None, "disk type"),
             (r"Haben Sie Ihre Systemdateien schon gerettet", "j\r", "backup question")]
    done = set()
    while m.alive():
        time.sleep(1)
        for pat, reply, why in rules:
            if pat not in done and m.find(pat):
                done.add(pat)
                if reply is None:
                    for _ in range(3):
                        m.send(" ", why)
                    m.send("\r", why + ": MC1325")
                else:
                    m.send(reply, why)
        if m.find(r"Syncing disks[^\n]*\n\s*Halt the processor"):
            say("A: 'Halt the processor' - switching off")
            time.sleep(5)
            m.stop()
            return True
        if m.find(r"panic:"):
            say("A: kernel panic")
            time.sleep(5)
            m.stop()
            return False
    say("A: MAME ended before 'Halt the Processor'")
    return False

def verify_login(m, user="mgast", password=None):
    # log in and wait for the SINIX menu. getty discards anything typed before it has
    # reopened the console, so let the prompt settle first; login then gives only a few
    # seconds for the password, so answer "Kennwort:" as soon as it shows.
    pats = (r"Kennwort:", r"Bitte waehlen", r"Falsche Angaben|Benutzerkennung:")
    for attempt in (1, 2):
        time.sleep(15)
        m.skip(*pats)
        m.send(user + "\r", f"login {user} (attempt {attempt})")
        end = time.time() + 120
        while time.time() < end and m.alive():
            time.sleep(0.3)
            if password is not None and m.find(pats[0]):
                # login flushes input when it turns echo off; type after that
                time.sleep(0.5)
                os.write(m.fd, (password + "\r").encode())
                say(f"{m.phase}: sent password for {user}")
            if m.find(r"Bitte waehlen"):
                say(f"{m.phase}: logged in as {user} - SINIX menu is up")
                time.sleep(5)
                return True
            if m.find(r"Falsche Angaben|Benutzerkennung:"):
                say(f"{m.phase}: login did not go through, back at the prompt")
                break
    say(f"{m.phase}: no SINIX menu after login")
    return False

def phase_verify():
    m = Machine("V", SECS_B, None)
    end = time.time() + 1800
    while m.alive() and time.time() < end:
        time.sleep(1)
        if m.find(r"sasiopen: no label SINIX found\s*\n:"):
            m.send("sa(1,0)sinix\r", "loader prompt, boot from disk")
        if m.find(r"eingeben \[jj\]"):
            m.send(time.strftime("86%m%d%H%M") + "\r", "date, year 1986")
        if m.find(r"Benutzerkennung:|login:"):
            say("V: login prompt")
            if V_USER == "-":
                say("V: leaving the machine up for manual use (console written to con-V.txt)")
                m.p.wait()
                return
            verify_login(m, V_USER, V_PASS)
            break
        if m.find(r"panic:"):
            say("V: kernel panic")
            break
    m.stop()

def phase_b():
    m = Machine("B", SECS_B, None)
    wanted = None
    while m.alive():
        time.sleep(1)
        if m.find(r"sasiopen: no label SINIX found\s*\n:"):
            m.send("sa(0,0)sinix\r", "loader prompt, boot from disk")
        r = m.find(r"Diskette (\S+) einlegen")
        if r:
            wanted = r.group(1)
            if wanted in DISKS:
                m.floppy(scratch(wanted))
                time.sleep(8)
                m.send("j\r", f"{wanted} inserted")
            else:
                say(f"B: asks for unknown diskette {wanted!r} - stopping")
                break
        if m.find(r"Falsche Diskette eingelegt"):
            say(f"B: installer says wrong diskette (wanted {wanted})")
        if m.find(r"RESTOR-Diskette[\s\S]*?eingelesen werden \? \(j/n\)"):
            m.send("n\r", "no RESTOR diskette (fresh install)")
        if m.find(r"eingeben \[jj\]"):
            # today's day and time with a 1986 year: a two-digit 26 would be 1926, before the epoch
            m.send(time.strftime("86%m%d%H%M") + "\r", "date, year 1986")
        if m.find(r"Auswahl des Tastaturtyps"):
            time.sleep(10)
            m.send("\r", "console keyboard type: international (first offered)")
        r = m.find(r"Bitte (\S+) Diskette aus dem Laufwerk nehmen")
        if r:
            m.floppy("unload")
        if m.find(r"Benutzerkennung:|login:"):
            say("B: login prompt - installation finished")
            verify_login(m)
            break
        for pat in (r"panic:", r"Halt the processor", r"Fehler beim Einrichten", r"Kundendienst"):
            if m.find(pat):
                say(f"B: stop condition {pat!r}")
                time.sleep(10)
                m.stop()
                return
    m.stop()

if __name__ == "__main__":
    if VERIFY:
        say(f"label {LABEL}, verify only: boot {HD} with no floppy")
        phase_verify()
    else:
        say(f"label {LABEL}, {SET}, work dir {WORK}")
        if phase_a():
            phase_b()
    for ph in "ABV":
        c = os.path.join(WORK, f"con-{ph}.txt")
        if os.path.exists(c):
            t = ANSI.sub("", open(c, encoding="latin1").read())
            marks = ["INSTALLATION EINES SINIX-SYSTEMS", "Plattentyp", "Platte wird formatiert",
                     "Minimal Version", "Halt the processor", "Diskette SINIX1", "SINIX7 Diskette eingelesen",
                     "Das Plattensystem ist fertig erzeugt", "Benutzerkennung:", "Bitte waehlen", "panic:",
                     "sensebytes"]
            say(f"{ph}: " + ", ".join(("+" if k in t else "-") + k for k in marks))
