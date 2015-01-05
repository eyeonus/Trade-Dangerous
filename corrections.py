# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "ARGETLAMH": "ARGETLáMH",
    "TAVYTERE": "ALRAI SECTOR ON-T B3-2",
    "PANTAA CEZISA": "GEORGE PANTAZIS",
    "DJALI": "HERCULIS SECTOR QD-T B3-4",
    "22 LYNCIS": "PEPPER",

#ADD_SYSTEMS_HERE
}

stations = {
    "AMARAK/WERNER VON SIEMENS VISON": "Werner Von Siemens Vision",
    "APOYOTA/FLINTSTATION": "Flint Station",
    "APOYOTA/HAHNRELAY": "Hahn Relay",
    "EKONIR/MOREYVISION": "Morey Vision",
    "TRELLA/TITTO COLONY": "Tito Colony",
    "ORERVE/WATSON SATION": "Watson Station",
    "MCC 467/ROB HUBBARD RING": "Ron Hubbard Ring",
    "GCRV 4654/HERZEFELD LANDING": DELETED,
    "LHS 220/CULPEPERCOLONY": DELETED,
    "LHS 64/WIBERG HANGAR": DELETED,    # "Hanger",
    "LP 862-184/MAYR HANGAR": "Mayr Hanger",
    "TYR/GLASHOW": DELETED,
    "EGOVAE/ENOATE MARKET": "Endate Market",
    "WOLF 1301/SAUNDER'S DIVE": "Saunders's Dive",
    "VEQUESS/AGNEWS FOLLY": "Agnews' Folly",
    "ONGKAMPAN/PATTERSON STATION:274": DELETED,
    "ZETA AQUILAE/OEFELIEN": DELETED,
    "ZETA AQUILAE/JULIAN GATEWAY": DELETED,
    "GROOMBRIDGE 1618/FRANKUN RING": "Franklin Ring",
    "WOLF 46/FISCHER CITY": DELETED,
    "LTT 9455/OLEARY VISION": DELETED,
    "HR 5451/MACDONALO HUB": DELETED,
    "HR 5451/MACOONALO HUB": DELETED,
    "V774 HERCULIS/MENOEL MINES": "Mendel Mines",
    "VALDA/CLAIRAUT OOCK": "Clairaut Dock",
    "LEESTI/GEORGELUCAS": "George Lucas",

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
    'COTTON': DELETED,
    'ALLOYS': DELETED,
    'PLASTICS': DELETED,
    'CONSUMER TECH': 'Consumer Technology',
    'DOM. APPLIANCES': 'Domestic Appliances',
    'FRUIT AND VEGETABLES': 'Fruit And Vegetables',
    'NON-LETHAL WPNS': 'Non-Lethal Weapons',
    'CENTAURI MEGA GIN': DELETED,

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

