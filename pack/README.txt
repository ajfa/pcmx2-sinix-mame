SIEMENS PC-MX2 WITH SINIX V2.0 (1986), EMULATED IN MAME, FOR WINDOWS
=====================================================================

Machine: Siemens PC-MX2 (1985), a multiuser Multibus system with an NS32016 CPU.
System:  SINIX V2.0, the Siemens Unix (kernel SINIX-M-C V2.0 Rev. 266, 22 April 1986).
Console: Siemens 97801 terminal, emulated, inside the same window.

The hard disk (Micropolis MC1325, 72 MB) already has SINIX V2.0 installed from the
original floppies SINIX0 to SINIX7 (set Nr. 31349). Nothing needs to be installed: the
emulator is inside the pack.


HOW TO USE IT
-------------

  SINIX.bat         Boots SINIX from your working disk (disk\sinix.img). The first time
                    it creates it the same way as SINIX-reset.bat. What you do is kept.

  SINIX-reset.bat   Throws away all changes and goes back to the freshly installed SINIX,
                    then boots like SINIX.bat.

Double click and wait. The boot runs at full speed until the login prompt, and the date
that SINIX asks for at boot is answered by itself. The login prompt comes after about a
minute, or about two when the disk has to be checked first (see below).


USERS
-----

  root    siemens    superuser, gets the shell (prompt #)
  admin   siemens    administrator, gets the SINIX menu with Systemverwaltung
  gast    siemens    guest with a shell
  mgast   (none)     menu guest, no password

These are the factory passwords given in the PC-MX2 installation guide. Nothing shows
while you type the password, and there are only a few seconds to type it: if you take too
long it asks for the user again without saying anything; just repeat.


THE KEYBOARD
------------

Type normally on your own keyboard: MAME translates each character to the 97801 key that
produces it (natural keyboard), so letters, digits and symbols come out as typed.

In the menus you choose with the letter and Enter ("Bitte waehlen! >"). A dot and HELP
give help.

Scroll Lock switches between "the keyboard goes to SINIX" and "the keyboard goes to MAME"
(in that mode Tab opens the MAME menu). To quit, close the window.


SOFTWARE PRODUCTS
-----------------

If the disk was set up with harness/products.py, it also has, installed with SINIX's own
product installer (admin, Systemverwaltung, "i - Installation von Softwareprodukten"):

  CES-I-A V2.0      C development system: cc, as, ld, adb, lex, yacc, make, the headers
                    in /usr/include and SCCS (admin, get, delta...).
  OBG V2.0          vi, ex, csh, nroff, tbl, neqn, spell, cpio, dd, od, cut, finger and
                    other tools, with the curses library.
  INFDEV V2.00      INFORMIX-SQL: isql (SQL menus), perform (screens), ace (reports) and
                    esqlc (SQL in C).
  PASCAL-XT V1.0A   Pascal compiler: pc program.p leaves the program in a.out.

To try it, as root:

  cd /tmp
  echo 'main(){puts("hello");}' > h.c
  cc -o h h.c
  ./h


SHUTTING DOWN PROPERLY
----------------------

As on the real machine:

  1. Log in as root.
  2. Type  /etc/haltsys  and Enter.
  3. Wait for "Halt the processor".
  4. Close the window.

Closing the window without shutting down breaks nothing: the next boot says so and
repairs the disk by itself (it takes a minute longer).


MESSAGES THAT LOOK LIKE ERRORS AND ARE NORMAL
---------------------------------------------

  RECAL-compl-stat: 15  sensb: 30 ... / READ -compl-stat: 15  sensb: 30 ...
  no sys-floppy, going to harddisk
  INIT -compl-stat: 15  sensb: 1E ...
      The monitor looks at the floppy drive first, which is empty, and then boots from
      the hard disk.

  warning: mounting unclean fs
  Das System wurde nicht ordnungsgemaess abgestellt ... Phase 1 ... Phase 5
      Last time the window was closed without shutting down. SINIX checks the disk by
      itself and carries on.

  Automatischer Wiederanlauf beginnt...
      "Automatic restart", after that check. Normal.

  Nothing after "125952+18200+9640=153792d=258C0x"
      Now and then the boot stops there. Close the window and start again.

  The date shows 1986
      On purpose: SINIX V2.0 keeps the year in two digits and 2026 does not fit. Today's
      day and time are used with the year 1986.


WHAT IS IN THE FOLDER
---------------------

  pcmx2.exe      MAME with the PC-MX2 driver and the fixes it needed.
  roms\          ROMs of the boards: CPU-AP, SERAD, Storager and the 97801 terminal.
  disk\          sinix-installed.img (never touched) and sinix.img (your disk).
  boot.lua       Answers the date and speeds up the boot. Used by SINIX.bat.
  data\          MAME configuration, created by itself.
  snap\          Screenshots you take with MAME (F12 in MAME mode).

Nothing is written outside this folder. To remove everything, delete the folder.
