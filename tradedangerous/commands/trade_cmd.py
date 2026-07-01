# tradedangerous/commands/trade_cmd.py
#
# Compatibility alias for the 'direct' command.
#
# 'trade trade ...' predates the rename to 'direct' (issue #241). It remains a
# first-class, supported alias -- not a deprecation -- and shares direct's
# parser and logic verbatim. The only thing that differs is the command name
# argparse advertises, so we re-export direct's surface and override `name`
# here. A bare `from .direct_cmd import *` would also pull in name='direct',
# making the registry try to register two commands under the same name; hence
# the explicit re-export plus the local name.
from __future__ import annotations

from .direct_cmd import (  # noqa: F401  (re-exported as this command's surface)
    needs,
    epilog,
    arguments,
    switches,
    run,
    render,
    validateRunArgumentsFast,
)

name = 'trade'
help = "Alias for the 'direct' command."
