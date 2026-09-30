# What was measured and fixed

All against `storager-lle` at `0147a62a34d`, booting Tenox's SINIX0 floppies
(`set1/mx2-001`, `set2/mx2-a03`) and the SINIX0 of the S3510 supplement on
archive.org. Measured with MAME Lua scripts (`-autoboot_script` with read and write taps
on the 68000 RAM, and the debugger run headless with `-debug -debugger none`), the
Storager v260 firmware disassembled, and temporary traces in the devices.

## Starting point

With the build pieces in patch 01 the branch boots the CPU-AP self test and the loader
reads the floppy, but stops at

    testend
    no sys-floppy, going to harddisk
    sasiopen: no label SINIX found
    :

The floppy is fine: cylinder 0 is FM with 128 byte sectors, sector 7 holds
`VOL1SINIX0 ... SIEMENS` and sector 8 `HDR1 NSC Boot`.

## 1. First floppy sector in the wrong slot (patch 02)

Per sector the firmware takes an IRQ6 (ID verify) and two IRQ5 that it tells apart by bit
0 of `[$7950]`: setup (`$7BA8`, sets the bit) and done (`$8018`, publishes the next chunk
in C800 and sends the current one to the host). On the first sector of a command:

1. the IRQ6 arrives before a chunk is allocated (`[$741e]=0`), so C800 is empty;
2. setup allocates the chunk (`[$741e]=2000`) and sets `[$7950]=1`;
3. the model sees an empty C800 and skips the sector;
4. on the retry setup takes another path and does not set the bit again. The done IRQ5
   is taken as another setup, sector 1 is never delivered and sector 2 lands in its
   chunk. Every sector ends up 128 bytes early and the label is not found.

Fix: on the first field of each floppy command, deposit only when `[$7950]` bit 0 is set,
in C800 if it is valid and otherwise in `[$741e]`; with the bit clear let the record come
round again. The same rule also removes an intermittent `sensebytes=1C` on later reads,
which happened when the verify IRQ6 found a chunk left over from the previous command.
Retrying only the data field (without the IRQ6) was tried first and is worse.

After it the loader finds the label and loads the NSC boot program
(`Load:text + data = 10392 + 2320`), then times out reading the kernel.

## 2. Reads that never reach the next cylinder (patch 03)

The track change is a state machine in `[$7a60]` (routine `$9398`): 0 computes the next
track and starts the seek `$6788`, 2 reopens the read (`$7346`, writes `[$7ABC]`), 1 polls
`$6bc2` until the head has settled, a software timer of `UIB+$18` = 70 ticks of 26 ms.
The model started presenting the new side as soon as `[$7ABC]` was written, so the whole
track went by inside the settle wait, its end of track was consumed as one more poll, and
the firmware waited for a track the model had already finished.

Fix: on floppy, start no new record while `[$7a60] == 1`. The kernel then loads:

    Boot: sa(22,0)sinix
    125952+18200+9640=153792d=258C0x

    SINIX-M-C V2.0 (Rev. 266) Tue Apr 22 16:19:53 MET 1986

    System 734k User 3362k
    using 143 buffers containing 417792 bytes of memory

## 3. The kernel dies on the first interrupt driven command (patch 04)

Runs ended about 30 s in with `Fatal error: abort during abort entry 0x000005e4`. The
kernel programs the NS32202 with `ELTG=0xfdaf`: IR3, the Storager, is level triggered and
stays asserted until the driver reads its register 0. The common interrupt entry at
`0x5e4` reads SVCT (`0xFF8602`) to learn which interrupt it is serving. MAME's ICU
recomputed SVCT from what was pending at that moment, and the acknowledge had already
cleared it, so the read returned `0x1f` (IR15) every time. With the edge triggered clock
and console nobody noticed; with IR3 held low the handler was never called, the kernel
reentered and overflowed its stack. The polled reads before it finished before the
interrupt timer, so the first real interrupt was a seek.

Fix: latch the vector at each real acknowledge and return it from SVCT.

## 4. `init` dies and its core fills the floppy (patch 05)

The root is a 4.2BSD FFS variant (magic `0x90545`, 4 KB blocks, 1 KB fragments) starting
at 256 byte sector 128. After a run it had a new 16 KB `/core` of `init`, exactly the free
space: `init` died, its dump filled the disk (`/: file system full`) and the kernel said
`panic: init died`. The last MMU fault of `init` was at `pc=0x2ca`, `MOVD R0, (SB)` in
crt0, writing to `0x0fc008`: SB held the value that the kernel has at address `0x20`, its
own module table. MAME's NS32000 read the module descriptor in `RETT`/`RETI` before
installing the restored PSR, so through the supervisor map.

Fix: read it with the restored PSR (`mem_read<u32>(ST_ODT, mod, psr & PSR_U)`). After it
the installer comes up (`INSTALLATION EINES SINIX-SYSTEMS`), offers
`RO202E / MC1303 / MC1323 / MC1325` and formats the disk.

## 5. Random disk errors under memory pressure (patch 08)

With the C compiler, vi and INFORMIX installed, compiling a Pascal program made the kernel
print `dm0d: sensebytes=0<ETYPE=0,ECODE=0,...> blkno=33280` and then kill processes with
`no swap space`. The failing command was a seek (`op=0b`) that the model had completed
normally; the sense that followed was all zeros.

The driver reads the command status from register 1, and the model built it from the byte
at `0x0fe782`, where the Storager firmware posts its verdict into the host IOPB. Rigid disk
commands at run time are completed in line by the model and never go through the
firmware, so that byte was whatever the host memory held. At boot it still held the last
firmware completion (`0x80`); once the kernel gave that page to a user process, any other
value read as an error. Sense also wrote `0x80` there to make its own status look clean,
which wrote into that process's memory.

Fix: commands completed in line report success themselves and nothing is written to host
memory. Firmware-backed commands (the floppy) still report the firmware's verdict.

## The installation

The installer switches the machine off halfway, as on the real hardware, so
`harness/install.py` does it in two MAME runs. Things that matter when driving it:

- Every dialog other than the floppy swaps is typed: the keyboard type list cycles with
  space and Enter takes the current one, then the RESTOR question, the date, the login.
- The login program discards what is typed before it reopens the console: wait for a
  new `Benutzerkennung:` before typing. After `Kennwort:` it waits only about 4 s of real
  time; type the password half a second after the prompt, because turning echo off
  flushes the input.
- Formatting takes about 10 minutes of real time here, phase B about 25.
- MAME does not act on SIGTERM in this setup; the harness kills it after 30 s.

Harmless messages seen with both sets: `df2c: sensebytes=1C ... blkno=982` once during
formatting, and `dm0b: sensebytes=0 ... blkno=5168`.

## Still open

- A warm restart after a floppy boot boots the floppy again only if the last read before
  the restart was on side 0; the firmware does not reselect the head (`E804`) before
  reading cylinder 0.
- The MC1325 image is a flat `.img`, so MAME makes up its geometry and the Storager trace
  prints `*** DISAGREE ***` against the UIB. The installer is happy with it.
