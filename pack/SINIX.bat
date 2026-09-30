@echo off
rem Siemens PC-MX2 with SINIX V2.0 on MAME, 97801 terminal in the window.
rem Uses disk\sinix.img (your working disk); if it does not exist yet, SINIX-reset.bat
rem creates it from the freshly installed one and boots. Everything MAME writes stays inside
rem this folder.
cd /d "%~dp0."
if exist "%~dp0disk\sinix.img" goto run
call "%~dp0SINIX-reset.bat" %*
exit /b
:run
if not exist "%~dp0data" mkdir "%~dp0data"
"%~dp0pcmx2.exe" pcmx2 -noreadconfig -rompath "%~dp0roms" ^
    -hard1 "%~dp0disk\sinix.img" -slot3:serad:port0 s97801 ^
    -natural -window -nomaximize -skip_gameinfo ^
    -autoboot_script "%~dp0boot.lua" ^
    -cfg_directory "%~dp0data\cfg" -nvram_directory "%~dp0data\nvram" ^
    -snapshot_directory "%~dp0snap" -diff_directory "%~dp0data\diff" ^
    -comment_directory "%~dp0data\comments" -share_directory "%~dp0data\share" %*
if errorlevel 1 (
    echo.
    echo MAME ended with an error. Read the message above.
    pause
)
