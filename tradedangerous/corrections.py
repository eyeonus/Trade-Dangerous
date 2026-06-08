# Provides an interface for correcting names that
# have changed in recent versions.

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "PANDAMONIUM": "PANDEMONIUM",
    "ARGETLÁMH": "ARGETLAMH",
    "LíFTHRUTI": "LIFTHRUTI",
    "MANTóAC": "MANTOAC",
    "NANTóAC": "NANTOAC",
}

stations = {
}

categories = {
}

items = {
    'POWER TRANSFER CONDUITS': 'Power Transfer Bus',
    'LOW TEMPERATURE DIAMOND': 'Low Temperature Diamonds',
    'COOLING HOSES': 'Micro-weave Cooling Hoses',
    'METHANOL MONOHYDRATE': 'Methanol Monohydrate Crystals',
    'OCCUPIED CRYOPOD': 'Occupied Escape Pod',
    'SALVAGEABLE WRECKAGE': 'Wreckage Components',
    'POLITICAL PRISONER': 'Political Prisoners',
    'HOSTAGE': 'Hostages',
    "VOID OPALS": "Void Opal",
}

def correctSystem(oldName):
    try:
        return systems[oldName.upper()]
    except KeyError:
        return oldName

def correctStation(systemName, oldName):
    try:
        return stations[systemName.upper() + "/" + oldName.upper()]
    except KeyError:
        return oldName

def correctCategory(oldName):
    try:
        return categories[oldName.upper()]
    except KeyError:
        return oldName

def correctItem(oldName):
    try:
        return items[oldName.upper()]
    except KeyError:
        return oldName


# ---- Lookup-key normalisation ----
# Single source of truth for the normalisation applied to System and Station
# names when building the lookup_name schema column and when resolving partial
# names. It lives here -- a dependency-free, top-level module -- so every writer
# of those rows (the resolver, the CSV importer, the spansh upsert, and the
# external listener) computes the same key without pulling in DB/ORM machinery.
# Two-stage rule (mirrors the historical TradeDB.normalizeTrans / trimTrans):
#   stage 1 -- uppercase a-z, delete  [ ] ( ) * + - . , { } :
#   stage 2 -- delete space and apostrophe

# Stage 1: uppercase a-z, delete [ ] ( ) * + - . , { } :
_normalize_trans = str.maketrans(
    'abcdefghijklmnopqrstuvwxyz',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    '[]()*+-.,{}:'
)
# Stage 2: delete space and apostrophe
_trim_trans = str.maketrans('', '', " '")


def normalize_str(s):
    """Return the two-stage normalised lookup key for *s*.

    Stage 1 uppercases and strips punctuation; stage 2 strips spaces and
    apostrophes. This is what populates System.lookup_name / Station.lookup_name
    and what partial-name candidate gathering compares against, so every
    producer of those rows must use this exact function.
    """
    return s.translate(_normalize_trans).translate(_trim_trans)
