@echo off
rem Throws away every change made on the working disk and starts again from the freshly
rem installed SINIX V2.0, then boots it.
cd /d "%~dp0."
echo Going back to the freshly installed SINIX disk (changes on the working disk are lost)...
copy /y "%~dp0disk\sinix-installed.img" "%~dp0disk\sinix.img" >nul
if errorlevel 1 (
    echo Could not copy the disk. Is SINIX open in another window?
    pause
    exit /b 1
)
call "%~dp0SINIX.bat" %*
