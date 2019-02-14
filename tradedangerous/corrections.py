# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "PANDAMONIUM": "PANDEMONIUM",
    "ARGETLÁMH": "ARGETLAMH",
    "LíFTHRUTI": "LIFTHRUTI",
    "MANTóAC": "MANTOAC",
    "NANTóAC": "NANTOAC",

#ADD_SYSTEMS_HERE
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
    'GALACTIC TRAVEL GUIDE': DELETED,
    'OCCUPIED CRYOPOD': 'Occupied Escape Pod',
    'Salvageable Wreckage': 'Wreckage Components', 
    'Political Prisoner': 'Political Prisoners',
    'Hostage': 'Hostages',
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
