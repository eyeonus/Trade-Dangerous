# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Utils
#
"""This modules contains various utils to be used internally.
"""

import re

__all__ = ['titleFixup']


def titleFixup(text: str) -> str:
    """
    Correct case in a word assuming the presence of titles/surnames,
    including 'McDonald', 'MacNair', 'McKilroy', and cases that
    python's title screws up such as "Smith's".
    """
    
    text = text.title()
    text = re.sub(
        r"\b(Mc)([a-z])",
        lambda match: match.group(1) + match.group(2).upper(),
        text
    )
    text = re.sub(
        r"\b(Mac)([bcdfgjklmnpqrstvwxyz])([a-z]{3,})",
        lambda m: m.group(1) + m.group(2).upper() + m.group(3),
        text
    )
    text = re.sub(
        r"\b(von|van|de|du|of)\b",
        lambda m: m.group(1).lower(),
        text
    )
    text = re.sub(r"'S\b", "'s", text)
    text = ''.join((text[0].upper(), text[1:]))
    
    return text
