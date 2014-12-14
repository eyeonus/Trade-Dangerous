# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    'MANTOAC': "Mantóac",
    "NANTOAC": "Nantóac",
    "LIFTHRUTI": "Lífthruti",
    "SETING": DELETED,

#ADD_SYSTEMS_HERE
}

stations = {
    "CHEMAKU/BARTOE PLATFORM": DELETED,
    "ERAVATE/ASKERMAN MARKET": "Ackerman Market",
    "YAKABUGAI/SEREBOV STATION": "Serebrov Station",
    "HALAI/GENKER STATION": "Cenker Station",
    "LFT 926/MEREDITH STATION": "Meredith City",
    "OPALA/ZAMK PLATFORM": "Zamka Platform",
    "G 139-50/FILIPCHENKO": "Filipchenko City",
    "AMARAK/WERNER VON SIEMENS VISON": "Werner Von Siemens Vision",
    "SETING/COX LANDING": DELETED,
    "APOYOTA/FLINTSTATION": "Flint Station",
    "APOYOTA/HAHNRELAY": "Hahn Relay",
    "EKONIR/MOREYVISION": "Morey Vision",
    "TRELLA/TITTO COLONY": "Tito Colony",
    "ORERVE/WATSON SATION": "Watson Station",

#ADD_STATIONS_HERE
}

categories = {
    'DRUGS':            'Legal Drugs',
    'SLAVES':           'Slavery',
}

items = {
    'HYDROGEN FUELS':   'Hydrogen Fuel',
    'MARINE SUPPLIES':  'Marine Equipment',
    'TERRAIN ENRICH SYS': 'Land Enrichment Systems',
    'HEL-STATIC FURNACES': 'Microbial Furnaces',
    'REACTIVE ARMOR': 'Reactive Armour',
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

