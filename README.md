# Siemens PC-MX2 with SINIX V2.0 in MAME

Patches to MAME that make the Siemens PC-MX2 (1985, Multibus, NS32016) install SINIX V2.0
from its original floppies onto an emulated Micropolis MC1325 hard disk, boot it to the
login prompt and run it with the Siemens 97801 terminal as console.

They go on top of David Rand's
[`storager-lle`](https://github.com/davidlrand/mame/tree/storager-lle) branch of MAME,
which has the Interphase Storager disk controller (a 68000 running its own firmware) and
the rest of the PC-MX2 bring-up. The PC-MX2 driver itself is by Patrick Mackinlay.

No Siemens software is included here. The floppies are the "PC-MX2 von Udo" set in
Tenox's archive, <https://tenox.pdp-11.net/os/sinix/rechner.rar>, under
`rechner/mx-rm/pc-mx2/images/imd/`: `set1/mx2-001..008` and `set2/mx2-a03..a10` are
SINIX0 to SINIX7, two copies of the base distribution.

## What works

- The whole installation, unattended: disk type, formatting, the minimal system, then
  SINIX1 to SINIX7 swapped in when the installer asks, keyboard type, date, multiuser
  mode. Done with both sets.
- Booting the installed disk to `Benutzerkennung:` and logging in: `mgast` (menu guest,
  no password) and `admin` / `siemens` (the factory password from the installation guide)
  get the SINIX menu. `root`, `gast` and `uucp` share the `admin` password hash.
- The 97801 terminal in the MAME window with MAME's natural keyboard, and a clean
  shutdown with `/etc/haltsys`.

Not looked at: tape, Ethernet (ExeLAN), the supplements (S3510 service floppies, CES,
MES and the others in Tenox's archive). A warm restart after a floppy boot does not always
find the floppy again; see [docs/NOTES.md](docs/NOTES.md).

## The patches

Against `storager-lle` at `0147a62a34d` (21 August 2026), applied in order:

| Patch | What it does |
|---|---|
| `01-storager-lle-build.patch` | Pieces the branch needs to build here: the Storager back in `bus.lua` and in slot 1 of `pcmx2`, headers for CPU-AP, SERAD, SCN2681, NS32000 wait states and `floppy_image_device::get_image()`, the SERAD Multibus lock and interrupt strobe, and the floppy swap callback |
| `02-storager-first-sector.patch` | First sector of each floppy read lands in the slot the firmware armed, instead of shifting every sector one slot |
| `03-storager-head-settle.patch` | No new floppy sector while the firmware waits for the head to settle, so multitrack reads cross to the next cylinder |
| `04-ns32202-svct.patch` | NS32202 ICU: SVCT returns the interrupt being serviced instead of recomputing it; without it the kernel dispatches everything as IR15 and overflows its stack on the first level interrupt |
| `05-ns32000-rett-sb.patch` | NS32000: `RETT` and `RETI` read the module descriptor with the restored PSR; without it `init` starts with the kernel's SB and dies |
| `06-s97801-terminal.patch` | The Siemens 97801 terminal, keyboard and layout from MAME master, as an RS-232 option for the SERAD console port |
| `07-pcmx2-working.patch` | Drops `MACHINE_NOT_WORKING` from `pcmx2` |

Patches 04 and 05 change devices that other MAME machines use (pc532 among them); they
were only run with the PC-MX2. How each problem was found is in
[docs/NOTES.md](docs/NOTES.md).

## Layout

    patches/    the changes to MAME, in order
    harness/    build (Linux and MSYS2), unattended install and login check
    tools/      reading files from the installed disk, and the termcap patch
    pack/       launchers, boot helper and README of the Windows pack
    docs/       what was measured and fixed

## Building

    harness/build.sh

clones the branch into `mame/`, checks out `0147a62a34d`, applies the patches and builds
the `pcmx2` subtarget (`MAME_SRC` to put the tree elsewhere). For Windows, see the top of
`harness/build-windows.sh` (MSYS2).

The ROM sets go in `roms/`: `cpuap.zip`, `serad.zip`, `storager.zip`, `s97801.zip`,
`s97801_kbd.zip` and `s97801_device.zip`.

## Installing

Put Tenox's IMD files in `floppies/set1/` and `floppies/set2/`. On Linux:

    harness/install.py s1 set1

Phase A boots SINIX0 on a blank MC1325, answers the installer and stops when it halts the
machine; phase B boots the disk and feeds it SINIX1 to SINIX7 through
`harness/floppies.lua`, which loads floppy images into the running machine. At the end it
logs in as `mgast` and waits for the menu. The disk is `work/s1/hd.img`. It took 20 to 35 minutes here.

    harness/install.py s1 verify admin siemens

boots that disk again and logs in. With user `-` it leaves the machine at the login prompt.
The console is a pty and MAME runs without a window.

Before using the disk with the 97801 in a window, run

    tools/termcap.py work/s1/hd.img patch

It makes the console use the German key table with the ASCII display set, which is what
MAME's natural keyboard sends. SINIX asks for the date at every boot: answer with year
86 (`86MMDDhhmm`), because a two digit 26 is 1926, before the Unix epoch.

## Windows pack

A folder with `pcmx2.exe`, `roms\`, the installed disk as `disk\sinix-installed.img` and
the files in [pack/](pack/). `SINIX.bat` boots it in a window with the 97801 and
`boot.lua` answers the date; [pack/README.txt](pack/README.txt) explains how to use it and
shut it down.

## License

BSD-3-Clause, see [LICENSE](LICENSE), like the MAME files the patches change. The
Storager and 97801 code keeps the headers of its authors.
