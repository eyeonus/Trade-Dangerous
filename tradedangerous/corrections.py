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
    "VOID OPAL": "Void Opals",
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
