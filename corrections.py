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
    "21 DRACO/ROBERTS PORT": DELETED,
    "37 XI BOOTIS/SCHIRRA PLANT": "Schirba Plant",
    "ADENETS/ALLEN HORIZONS": DELETED,
    "AKHENATEN/WANG PLATFORM": DELETED,
    "ALBICEVCI/DUBROVOLSKI SURVEY": "Dobrovolski Survey",
    "AMAIT/LOPEZ DE VILLALOBOS": "Lopez De Villalobos Prospect",
    "AMARAK/WERNER VON SIEMENS VISON": "Werner Von Siemens Vision",
    "ANAPOS/HERSCHEL PLATFORM": "Herschel Plant",
    "AO QIN/CHAPMAN HUB": DELETED,
    "APOYOTA/FLINTSTATION": "Flint Station",
    "APOYOTA/HAHNRELAY": "Hahn Relay",
    "AULIN/ALUIN ENTERPIRSE": "Aulin Enterprise",
    "BD+13 693/DRUMMOND`S PROGRESS": "Drummond's Progress",
    "BD+65 1846/SHARGIN BEACON": DELETED,
    "BOLG/MOXONS MOJO": "Moxon's Mojo",
    "CEMIESS/TITUS STATION": "Titius Station",
    "DORIS/ISHERWOOD DOCK": DELETED,
    "DT VIRGINIS/CHUN STATION": "Chun Vision",
    "EGOVAE/ENOATE MARKET": "Endate Market",
    "EKONIR/MOREYVISION": "Morey Vision",
    "GCRV 4654/HERZEFELD LANDING": "Herzfeld Landing",
    "GROOMBRIDGE 1618/FRANKUN RING": "Franklin Ring",
    "HDS 1879/HEDIN ORBITAL": DELETED,
    "HIP 4907/EDISON PLATFORM": DELETED,
    "HR 5451/MACDONALO HUB": "MacDonald Hub",
    "HR 5451/MACOONALD HUB": "MacDonald Hub",
    "HR 5451/MACOONALO HUB": "MacDonald Hub",
    "JAWOLA/SUTCLIFFEPLATFORM": "Sutcliffe Platform",
    "KANOS/LEE STATION": DELETED,
    "LEESTI/GEORGELUCAS": "George Lucas",
    "LFT 1446/BOSCH SETTLEMENT": DELETED,
    "LHS 1101/BONDAR CITY": DELETED,
    "LHS 220/CULPEPERCOLONY": "Culpeper Colony",
    "LHS 250/KOVALESKY ENTERPRISE": "Kovalevsky Enterprise",
    "LHS 2884/ABNETT PLATEFORM": "Abnett Platform",
    "LHS 64/WIBERG HANGAR": "Wiberg Hanger",    # "Hanger",
    "LP 322-836/BOLOTOV PORT": DELETED,
    "LP 51-17/ARCHAMBAULT HORIZONS": DELETED,
    "LP 811-17/STJEPAN SELJAN PORT": DELETED,
    "LP 862-184/MAYR HANGAR": "Mayr Hanger",
    "LTT 15449/REILLI DOCK": "Reilly Dock",
    "LTT 7548/ALEXANDRIA RINF": "Alexandria Ring",
    "LTT 9455/OLEARY VISION": "O'Leary Vision",
    "MANNONA/THORNYCROFY PENAL COLONY": "Thornycroft Penal Colony",
    "MCC 467/ROB HUBBARD RING": "Ron Hubbard Ring",
    "MOKOSH/LUBEN ORBITAL": "Lubin Orbital",
    "NLTT 49528/O‹CONNOR LANDING": "O'Connor Landing",
    "ONGKAMPAN/PATTERSON STATION:274": "Patterson Station",
    "OPALA/ZAMK PLATFORM": "Zamka Platform",
    "ORERVE/WATSON SATION": "Watson Station",
    "PANGLUYA/BRADBURYWORKS": "Bradbury Works",
    "PERENDI/SHEPHERD INSTALLATION": DELETED,
    "RAHU/LEBEDEV BEACON": DELETED,
    "RHO CANCRI/HAMILTON R,SERVE": "Hamilton Reserve",
    "RHO CANCRI/HAMILTON R�SERVE": "Hamilton Reserve",
    "STEIN 2051/TREVITHICK PORT": DELETED,
    "TENG YEH/GARAN SURVERY": "Garan Survey",
    "TIETHAY/SANTOS PLANT1": DELETED,
    "TRELLA/TITTO COLONY": "Tito Colony",
    "TYR/GLASHOW": "Glashow Dock",
    "V774 HERCULIS/MENDEL MINES'": "Mendel Mines",
    "V774 HERCULIS/MENOEL MINES": "Mendel Mines",
    "V989 CASSIOPEIAE/LOW WORKS": DELETED,
    "VALDA/CLAIRAUT OOCK": "Clairaut Dock",
    "VEQUESS/AGNEWS FOLLY": "Agnews' Folly",
    "WOLF 1301/SAUNDER'S DIVE": "Saunders's Dive",
    "WOLF 46/FISCHER CITY": "Fischer Station",
    "YAKABUGAI/SEREBOV STATION": "Serebrov Station",
    "YAKABUGAI/SEREBROV": "Serebrov Station",
    "YANYAN/MORYN CITY": "Morin City",
    "ZETA AQUILAE/JULIAN GATEWAY": DELETED,
    "ZETA AQUILAE/OEFELIEN": "Oefelein Plant",
    "ZETA TRIANGULI AUSTRALIS/GUEST CITY2": "Guest City",

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

