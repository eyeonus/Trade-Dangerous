# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "22 LYNCIS": "PEPPER",
    "ALANI": DELETED,
    "DJALI": "HERCULIS SECTOR QD-T B3-4",
    "PANTAA CEZISA": "GEORGE PANTAZIS",
    "TAVYTERE": "ALRAI SECTOR ON-T B3-2",
    "BODB DJEDI": "BODEDI",

#ADD_SYSTEMS_HERE
}

stations = {
    "ADLIVUN/ABL SURVEY":                   DELETED,
    "AKHENATEN/WANG PLATFORM":              DELETED,
    "ALPHA FORNACIS/BENNET PORT":           DELETED,
    "AO QIN/CHAPMAN HUB":                   DELETED,
    "BALDUR/DUTTON STATION":                DELETED,
    "BALTAH'SINE/BALTAH''SINE STATION":     DELETED,
    "BALTAH'SINE/BALTAH'SINE STATION":      DELETED,
    "BALTAH'SINE/BALTHAISINE STATION":      DELETED,
    "BD+65 1846/SHARGIN BEACON":            DELETED,
    "COCIJO/HARRY MOORE 6 CO":              DELETED,
    "COSI/JU LIAN CITY":                    DELETED,
    "CPD-28 332/WI N N E GATEWAY":          DELETED,
    "DAJOAR/MACQUORN TERMINAL":             DELETED,
    "DITAE/DITAE":                          DELETED,
    "DORIS/ISHERWOOD DOCK":                 DELETED,
    "ERAVATE/ERAVATE":                      DELETED,
    "GABIETYE/GABIETYE":                    DELETED,
    "HDS 1879/HEDIN ORBITAL":               DELETED,
    "HIP 4907/EDISON PLATFORM":             DELETED,
    "HIP 69913/KONORATYEV OUTPOST":         DELETED,
    "KANOS/LEE STATION":                    DELETED,
    "LFT 1446/BOSCH SETTLEMENT":            DELETED,
    "LHS 1101/BONDAR CITY":                 DELETED,
    "LHS 1453/SAAVEORA PORT":               DELETED,
    "LOVEDU/OIVIS PLATFORM":                DELETED,
    "LP 322-836/BOLOTOV PORT":              DELETED,
    "LP 51-17/ARCHAMBAULT HORIZONS":        DELETED,
    "LP 811-17/STJEPAN SELJAN PORT":        DELETED,
    "LTT 1349/NORIFRA PORT":                DELETED,
    "OLWAIN/J. G. BALLARD TERMINAL":        DELETED,
    "RAHU/LEBEDEV BEACON":                  DELETED,
    "ROSMERTA/DHN ORBITAL":                 DELETED,
    "ROSMERTA/RHN ORBITAL":                 DELETED,
    "TANMARK/CASSI E-L-PEIA":               DELETED,
    "THUNDERBIRD/QUIMPY PORT":              DELETED,
    "ZETA AQUILAE/JULIAN GATEWAY":          DELETED,
    "ZETA AQUILAE/MOHMAND HOLOINGS":        DELETED,
    "ZETA AQUILAE/MOHMANO HOLDINGS":        DELETED,

#ADD_STATIONS_HERE
    "FK5 2550/WU INDT GATEWAY":             DELETED,
    "BRANI/ARMSTRONG STATION":              DELETED,
    "BRANI/BRAHE HUB":                      DELETED,
    "BRANI/DIRAC ENTERPRISE":               DELETED,
    "BRANI/NADDODDUR TERMINAL":             DELETED,
    "BRANI/RIDE RING":                      DELETED,
    "BRANI/WALLACE DOCK":                   DELETED,
    "BETA HYDRI/EOMONDSON HIGH M'''":       DELETED,
    "BETA HYDRI/EOMONDSON HIGH M''":        DELETED,
    "BETA HYDRI/EOMONDSON HIGH M'":         DELETED,
    "BETA HYDRI/FRANKLIN RINGX":            DELETED,
    "GEORGE PANTAZIS/ZAM IKA PLATFORM":     DELETED,
    "GEORGE PANTAZIS/ZAM R PLATFORM":       DELETED,
    "HIP 80364/STASHEFF 'LONY":             DELETED,
    "LALANDE 4141/4A5O4D":                  DELETED,
    "LALANDE 4141/4A5 -O4D":                DELETED,
    "LALANDE 4141/4A5040":                  DELETED,
    "LTT 537/G 1RSHTEIN H 1B":              DELETED,
    "LTT 537/RI ERRHTFIN HI BR":            DELETED,
    "MORTEN/VE .LAZQU IEZ STATION":         DELETED,
    "NUKURU/HALLE R PO RT":                 DELETED,
    "PANDAMONIUM/RIEDRICH PETERS RING":     DELETED,
    "PANDAMONIUM/.RILDRICH PLTERS RING":    DELETED,
    "PANDAMONIUM/RILDRICH PLTERS RING":     DELETED,
    "WOLF 1481/VE .LAZQU IEZ GATEWAY":      DELETED,
    "BALMUNG/RU IPPE .LT STATION":          DELETED,
    "VOLOWAHKU/WATI' MINE":                 DELETED,
    "GLIESE 868/ALVARADO RING":             DELETED,
    "GLIESE 868/FEYNMAN TERMINAL":          DELETED,
    "TOXANDJI/TSU NENAGA ORBITAL":          DELETED,
}

categories = {
    'DRUGS':            'Legal Drugs',
    'SLAVES':           'Slavery',
}

items = {
    'CONSUMER TECH': 'Consumer Technology',
    'DOM. APPLIANCES': 'Domestic Appliances',
    'FRUIT AND VEGETABLES': 'Fruit And Vegetables',
    'HEL-STATIC FURNACES': 'Microbial Furnaces',
    'HYDROGEN FUELS':   'Hydrogen Fuel',
    'MARINE SUPPLIES':  'Marine Equipment',
    'NON-LETHAL WPNS': 'Non-Lethal Weapons',
    'REACTIVE ARMOR': 'Reactive Armour',
    'TERRAIN ENRICH SYS': 'Land Enrichment Systems',

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

