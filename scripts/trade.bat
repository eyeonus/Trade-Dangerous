@echo off
rem --== Set default values below to prevent being asked each run ==--
set DEFAULT_CAPACITY=
set DEFAULT_LIGHTYEARS=
set DEFAULT_HOPS=
set DEFAULT_JUMPS=
set DEFAULT_AGE=
rem --== Set default values above to prevent being asked each run ==--

set /P update=Update database from maddavo? (Y\N): 
if /I not "%update%"=="Y" goto menu
:update
..\trade.py import --plug=maddavo --option=stncsv --option=syscsv -v
echo Update Complete
pause
:menu
cls
set /P menu=(U)pdate, (Q)uick Update, (I)mport, (P)references or (R)un: 
if /I "%menu%"=="U" goto update
if /I "%menu%"=="Q" goto quickupdate
if /I "%menu%"=="I" goto import
if /I "%menu%"=="P" goto preferences
if /I "%menu%"=="R" goto run
echo Invalid Selection
pause
goto menu
:quickupdate
..\trade.py import --plug=maddavo -v
echo Quick Update Complete
pause
goto menu
:preferences
set /P capacity=Capacity in Tons[%DEFAULT_CAPACITY%]: 
set /P lightyears=Range in Light Years[%DEFAULT_LIGHTYEARS%]: 
set /P hops=Number of station visits[%DEFAULT_HOPS%]: 
set /P jumps=Number of jumps between stations[%DEFAULT_JUMPS%]: 
set /P age=Max age of data in Days[%DEFAULT_AGE%]: 
echo Preferences set
pause
goto menu
:import
..\trade.py import import.prices -vvv
echo Import Complete
pause
goto menu
:run
set /P credits=Credits: 
set /P location=Start Location: 
if "%DEFAULT_CAPACITY%"=="" if "%capacity%"=="" set /P capacity=Capacity in Tons: 
if "%DEFAULT_LIGHTYEARS%"=="" if "%lightyears%"=="" set /P lightyears=Range in Light Years: 
if "%DEFAULT_HOPS%"=="" if "%hops%"=="" set /P hops=Number of station visits: 
if "%DEFAULT_JUMPS%"=="" if "%jumps%"=="" set /P jumps=Number of jumps between stations: 
if "%DEFAULT_AGE%"=="" if "%age%"=="" set /P age=Max age of data in Days: 
if "%capacity%"=="" set capacity=%DEFAULT_CAPACITY%
if "%lightyears%"=="" set lightyears=%DEFAULT_LIGHTYEARS%
if "%hops%"=="" set hops=%DEFAULT_HOPS%
if "%jumps%"=="" set jumps=%DEFAULT_JUMPS%
if "%age%"=="" set age=%DEFAULT_AGE%
..\trade.py run --cap=%capacity% --ly=%lightyears% -vvv --cr=%credits% --fr="%location%" -MD=%age% --hops %hops% --jum %jumps%
pause
goto menu
