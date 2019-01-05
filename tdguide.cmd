@echo off
SET mypath=%~dp0
SET scriptpath=%mypath:~0,-1%


python "%scriptpath%\tdguide.py" %*