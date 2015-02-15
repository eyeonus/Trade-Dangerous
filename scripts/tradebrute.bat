@echo off
CLS
Echo Trade Dangerous Batch script Ver 1.0 by Bruteman.
Echo Please note all questions must be answered in lower case no CAPS LOCK please!
Echo This Script outputs your run to a text document you can easily open and view.
Echo.
Echo -------Warning------- 
Echo.
Echo This script will overwrite any output file named the same.
Echo I.E. if you make a run and call it run1 it will make run1.txt
Echo If you run it again with the same output name run1.txt will be overwritten.
Echo You have been Warned!
Echo.


Set /p python= "Where is Python.exe? (Enter your path e.g. c:\python34) :"
goto :Start


:Start
Set /p update= "Do you want to update your trade data? (y/n) :"
If %update% ==y (goto :update) else (goto :Setup)


:update
%python%\python.exe trade.py import --plug=maddavo --opt=systems --opt=stations
goto :Setup


:Setup
Set /p textdoc= "What do you want to name the text document? (e.g. run1 = run1.txt) :"
Set /p capacity= "How much cargo space can you carry? :"
Set /p credits= "How much Credits do you have? :"
Set /p lyper= "How far can you jump loaded? (00.00) :"
Set /p emptyly= "How far can you jump empty? (00.00) :"
Set /p from= "Where are you now? enter(System/Station) no spaces) :"
Echo.
Echo Next question is where you're going to errors may happen in making your run if you set a destination but do not have enough hops or jumps to get there. Please if you're getting errors adjust your Jumps and Hops or enter "1" for anywhere.
Echo.
Echo Because of the problems with setting a destination currenlty it will try and get you within 2 jumps of where your asking.
Echo.
Set /p to= "Where are you going to? enter(System/Station) no spaces or (1) for anywhere :"
Set /p hops= "How may trade hops do you want? (enter a number 1-10) :"
Set /p jumps= "How many jumps are you willing to make between hops? (enter a number 1-10) :"
Set /p maxdays= "how many days old of data do you want to use? (1 - 30) :"
goto :Run


:Run
Echo.
Echo I am now building your run this can take a while depending on your choices.
Echo Give it a good 5 mins if it does not come back hit CTRL-C a few times to cancel... 
Echo.
If %to% ==1 (goto :Run1) else (goto :Run2)


Rem - Run1 = a command with any destination
:Run1
%python%\python.exe trade.py run --cap %capacity% --cr %credits% --ly-p %lyper% --empty-ly %emptyly% --from %from% --hop %hops% --jump %jumps% --max %maxdays% -vvv >%textdoc%.txt
goto :Done


Rem - Run 2 = a command with a set destination
:Run2
%python%\python.exe trade.py run --cap %capacity% --cr %credits% --ly-p %lyper% --empty-ly %emptyly% --from %from% --to %to% --end 2 --hop %hops% --jump %jumps% --max %maxdays% -vvv >%textdoc%.txt
goto :Done


:Done
Echo.
Echo Either you have an error or I finished the run look inside the folder for your text document.
Echo. 
Set /p again= "Do you want to make a new run or exit? (y/e) "
If %again% ==y (goto :Start) else (goto :End)


:End
Echo Goodbye thanks for using Trade Dangerous Batch script by Bruteman!
Pause

