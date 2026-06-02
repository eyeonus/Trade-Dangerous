"""Display-label lookup tables for command output.

Small code -> human-label maps used by the commands purely to render and sort
station attributes (market / planetary / fleet / settlement state, and
landing-pad size) in their output. They live here, separate from any database
module, so a command need not import a database class just to format a column.

The longer-form "Ext" variants the old code carried are not reproduced here —
nothing references them any more.
"""

# Y/N/? attributes share the same label set; kept as separate names so call
# sites read clearly and the maps can diverge later without touching callers.
marketStates     = {'?': '?', 'Y': 'Yes', 'N': 'No'}
planetStates     = {'?': '?', 'Y': 'Yes', 'N': 'No'}
fleetStates      = {'?': '?', 'Y': 'Yes', 'N': 'No'}
settlementStates = {'?': '?', 'Y': 'Yes', 'N': 'No'}

# Landing-pad size code -> short label.
padSizes         = {'?': '?', 'S': 'Sml', 'M': 'Med', 'L': 'Lrg'}
