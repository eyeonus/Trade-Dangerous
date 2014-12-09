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
For Windows users, you'll need "bash" from the msysgit package. You
can download it here: http://msysgit.github.io/

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


-Oliver

