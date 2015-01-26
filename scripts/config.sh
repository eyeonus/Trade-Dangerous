### TradeDangerous script configuration
# This file is just a bash script that sets several standard variables.
# It is loaded by the various 'tdxxx' scripts.

# How to launch trade dangerous
TRADEPY="${TRADEDIR:-.}/trade.py"

### COMMANDER/SHIP CONFIGURATION
#

# Put your name here for absolutely no reason at all, *yet*
CMDR="YourName"

# Current credit balance
CR=270742

# Set the position of the update window relative to top-right of screen
UPD_ARGS="-wx=-40 -wy=40"

# After a given number of hops, discard candidates that have scored less
# than the given percentage of the best candidate.
PRUNE_HOPS=3        # after 3 hops
PRUNE_SCORE=20      # percentage

# You can only have one set of variables "live" at a time, comment out
# old ships while you are not flying them, then you can just uncomment
# them later on.

# Tweaked Hauler
CAP=20
EMPTYLY=16.53
MAXLY=9.23
JUMPS=6


# Crappy Sidewinder
#CAP=4
#MAXLY=9.02
#EMPTYLY=10.04
#JUMPS=4
#CR=10203

