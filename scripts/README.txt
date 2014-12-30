I'm hoping that someone more adept at creating user interfaces will
come along and create a front-end for TD; I'm not an elitist who is
bent on command-line world domination.

This directory is for collections of "scripts" that are designed to
make it easier to use TD.

These scripts work by reading a configuration file, "config.sh", to
pass common arguments to several trade commands.

Copy the "config.sh" file from the scripts directory into your main
tradedangerous folder and edit as needed.

WINDOWS USERS: Read the <WINDOWS USERS> section before proceeding.

BASH USERS: Read the <BASH USERS> section for command line completion.

<THE SCRIPTS>:

The main magic here is the "config.sh" file, keep that up to date
and it will save you a lot of hassle.

The scripts use this to pass several of the TD parameters, such as
--cr, for you. You can always override these by adding your own
"--cr 1234" at the end of your command.

Add the scripts folder to your path and setup the environment
variable "TRADEDIR", and all you have to do is run the scripts
from the prompt:


$ tdbuyfrom <place> <item>
  Uses the 'buy' sub-command to try and find something near the
  station you name first.
   e.g  tdbuyfrom ibootis gold --ly 30


$ tdimad
  Downloads and imports data from maddavo
   e.g.  tdimad


$ tdnav <from> <to>
  Calculates a route from the first place to the second using your
  current "EMPTYLY" value.
   e.g  tdnav ibootis halai


$ tdrun <place>
  Calculate a trade run from <place> using the stored values for
  cr, cap, ly, empty and jumps.
   e.g  tdrun ibootis
  You can override any of these by supplying them,
   e.g. tdrun ibootis --ly 10

$ tdupd <station>
  Brings up the "update UI" for the specified station
   e.g  tdupd iboo/beag



<WINDOWS USERS>:

For Windows users, there are two options.

1. There is a basic trade.bat file which can import market data and
calculate simple trade runs. This trade.bat file can be run without
any further requirements once you have Python 3.4 installed. More
documentation for this option can be found in the <BATCH-FILE> section
of this file

2. To use the more powerful bash scripts you'll need "bash" from the
msysgit package. You can download it here: http://msysgit.github.io/

Once it's installed, press the Windows key and type: git

The first option you're prompted with should be "git bash".

When you run it, you should see something like a CMD window but the
prompt is a "$" instead of "C:\WINDOWS\>". This is a bash shell.

"Bash" uses Linux-style drive/directory name conventions, so you're
 C:\Users\MyName\TradeDangerous
would become
 /c/users/myname/tradedangerous

Figure out the bash-path to your trade and then type:

 $ ls /c/users/myname/tradedangerous/trade.py

to confirm that is indeed where your trade.py is.

In the likely case that you only use bash for TD, I recommend a few
minor settings tweaks. To change bash settings, type:

 $ start notepad ~/.bashrc

("~" means "my home directory", ".bashrc" is the config file)


Go to the end of the file, add a couple of blank lines and then add
the following lines:

  HISTSIZE=5000
  HISTFILESIZE=10000
  shopt -s histappend

  ### CHANGE THIS TO YOUR TradeDangerous path
  ### (Just don't include the 'trade.py' part
  export TRADEDIR="/c/users/myname/tradedangerous"

  # Add the scripts folder to the bash path
  export PATH="${TRADEDIR}/scripts:${PATH}"

  # Start all bash sessions from the trade dir
  cd "${TRADEDIR}"


Edit the "TRADEDIR" path to point to the folder containing trade.py

Save and quit notepad and type "exit" in the bash shell you have
open to end that bash session, and then open a new onew.

  $ ./trade.py

and confirm trade.py gives you its help text so all is good.

Unlike the windows Command prompt, bash will now remember your
command history across sessions.

Your shell is now also configured to treat the scripts in the
"scripts" folder of TD as commands so you can invoke them by
name.

OK - Now you can go back and read about the scripts :)

If you get an error
sh.exe": tdnav: command not found

Type the following from a prompt:

$ chmod a+x scripts/td*

</WINDOWS-USERS>

<BASH USERS>:

The file "td-completion.bash" does add an auto completion for the bash
shell. If you don't know what that is you better stick with the scripts
or learn something new.

Copy the file "td-completion.bash" into your $HOME directory and add the
following lines to your .bashrc file:

---8<---8<---8<---8<---8<---8<---8<---8<---
if [[ -f ~/td-completion.bash ]]; then
	. ~/td-completion.bash
fi
--->8--->8--->8--->8--->8--->8--->8--->8---

You need to exit and start the bash shell to make it work, or just
type in the command as seen above.

</BASH-USERS>

<BATCH-FILE>:

The trade.bat file was created by OpenSS to enable some simple usage
of Trade Dangerous without needing to install bash.

It currently implements:
1.  Updating the local Trade Dangerous database to reflect the
    database run at Maddavo's Market Share
    (http://www.davek.com.au/td/default.asp).
    This should give you a decent database to start running trade runs.
2.  Importing a local "import.prices" file such as would be produced
    from EliteOCR.
    This can be used to add more recent market information to
    the database.
3.  Setting/Overriding currently stored default values.
    This is simply an ease-of-use feature to prevent having to type
    values multiple times.
4.  Ask Trade Dangerous to calculate a trade run.
    This will ask a series of questions and calculate a run.

Set Up:

If you will be using the same ship for an extended period of time, it
would be a good idea to set the default values (located at the top of
the trade.bat file) before you run it to prevent being asked for the
values each time the file is run. You can edit the file by right
clicking it and choosing "Edit". This will enable you to set default
values for your ship's capacity and range as well as setting options
such as how many hops (station visits) and jumps (hyperdrive jumps) to
make as well as the maximum age of the market data to use.

When you set these values make sure you do not leave a space after the
"=" sign. Eg: set DEFAULT_CAPACITY=40

Usage:

Throughout the batch file the following conventions are used:
() Round brackets signify the letter to enter for that part of the menu.
   (I)n this example you would enter "i" and press enter
[] Square brackets signify the default value that has been set in the
   "Set Up" section above. This value will be automatically used if
   you press enter

When the batch file is first run it will ask if you want it to update
the local database to match Maddavo's Market Share. It is generally a
good idea to do this to ensure you have the most recent trade data to
work with. This is highly recommended for the first run of the batch
file to make sure there is actually some data to work with.

Main Menu:

The main menu will appear as such:
(U)pdate, (Q)uick Update, (I)mport, (P)references or (R)un
Each option is detailed below.

  Update:
  This is the same update that is run when the batch file is first
  opened. It will obtain the latest market data from Maddavo.

  Quick Update:
  This update will only update the latest market data from Maddavo.
  It will not update the Systems and Stations data. Useful if you just
  want new trade prices.

  Import:
  Import local market data from "import.prices". If you are using
  EliteOCR you can set the "export directory" in EliteOCR's
  preferences to match the main directory of Trade Dangerous
  (not the scripts folder) and when you choose "Export Trade
  Dangerous" in EliteOCR it should be placed in the right location to
  simply choose Import from the batch file's main menu.

  Preferences:
  These are the values used to calculate trade runs. You can use this
  to override the values set under the "Set Up" section above.

  Run:
  This is where you can start making credits. It will ask you for your
  current credits and location and ask Trade Dangerous to calculate a
  route according to the default values set above. If these values
  have not been set, you will be asked for them and they will be stored
  for the rest of the batch file session. They can be changed again
  in the preferences option from the main menu.

</BATCH-FILE>

-Oliver

