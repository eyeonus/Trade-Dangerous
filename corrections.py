# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "22 LYNCIS": "PEPPER",
    "ALANI": DELETED,
    "ARGETLAMH": "ARGETLáMH",
    "DJALI": "HERCULIS SECTOR QD-T B3-4",
    "PANTAA CEZISA": "GEORGE PANTAZIS",
    "TAVYTERE": "ALRAI SECTOR ON-T B3-2",

#ADD_SYSTEMS_HERE
}

stations = {
    "ADLIVUN/ABL SURVEY":                   DELETED,
    "AKHENATEN/WANG PLATFORM":              DELETED,
    "ALBICEVCI/DUBROVOLSKI SURVEY":         "Dobrovolski Survey",
    "ALPHA FORNACIS/BENNET PORT":           DELETED,
    "AMAIT/LOPEZ DE VILLALOBOS":            "Lopez De Villalobos Prospect",
    "AMARAK/WERNER VON SIEMENS VISON":      "Werner Von Siemens Vision",
    "ANAPOS/HERSCHEL PLATFORM":             "Herschel Plant",
    "AO QIN/CHAPMAN HUB":                   DELETED,
    "AULIN/ALUIN ENTERPIRSE":               "Aulin Enterprise",
    "BALDUR/DUTTON STATION":                DELETED,
    "BALTAH'SINE/BALTAH''SINE STATION":     DELETED,
    "BALTAH'SINE/BALTHAISINE STATION":      DELETED,
    "BD+65 1846/SHARGIN BEACON":            DELETED,
    "BOLG/MOXONS MOJO":                     "Moxon's Mojo",
    "CEMIESS/TITUS STATION":                "Titius Station",
    "COCIJO/HARRY MOORE 6 CO":              DELETED,
    "COSI/JU LIAN CITY":                    DELETED,
    "CPD-28 332/WI N N E GATEWAY":          DELETED,
    "DAJOAR/MACQUORN TERMINAL":             DELETED,
    "DITAE/DITAE":                          DELETED,
    "DORIS/ISHERWOOD DOCK":                 DELETED,
    "DT VIRGINIS/CHUN STATION":             "Chun Vision",
    "EGOVAE/ENOATE MARKET":                 "Endate Market",
    "EKONIR/MOREYVISION":                   "Morey Vision",
    "ERAVATE/ERAVATE":                      DELETED,
    "GABIETYE/GABIETYE":                    DELETED,
    "GCRV 4654/HERZEFELD LANDING":          "Herzfeld Landing",
    "HDS 1879/HEDIN ORBITAL":               DELETED,
    "HIP 4907/EDISON PLATFORM":             DELETED,
    "HIP 69913/KONORATYEV OUTPOST":         DELETED,
    "KANOS/LEE STATION":                    DELETED,
    "KHOLEDO/LOPEZ DE DILLALOBOS COLONY":   "Lopez De Villalobos Colony",
    "LFT 1446/BOSCH SETTLEMENT":            DELETED,
    "LHS 1101/BONDAR CITY":                 DELETED,
    "LHS 1453/SAAVEORA PORT":               DELETED,
    "LHS 250/KOVALESKY ENTERPRISE":         "Kovalevsky Enterprise",
    "LHS 53/OCONNOR SETTLEMENT":            "O'Connor Settlement",
    "LHS 64/WIBERG HANGAR":                 "Wiberg Hanger",    # "Hanger",
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
    "VEQUESS/AGNEWS FOLLY":                 "Agnews' Folly",
    "ZETA AQUILAE/JULIAN GATEWAY":          DELETED,
    "ZETA AQUILAE/MOHMAND HOLOINGS":        DELETED,
    "ZETA AQUILAE/MOHMANO HOLDINGS":        DELETED,
    "ZETA TRIANGULI AUSTRALIS/GUEST CITY2": "Guest City",

#ADD_STATIONS_HERE
    "FK5 2550/WU INDT GATEWAY":             DELETED,
    "BRANI/Armstrong Station":              DELETED,
    "BRANI/Brahe Hub":                      DELETED,
    "BRANI/Dirac Enterprise":               DELETED,
    "BRANI/Naddoddur Terminal":             DELETED,
    "BRANI/Ride Ring":                      DELETED,
    "BRANI/Wallace Dock":                   DELETED,
}

categories = {
    'DRUGS':            'Legal Drugs',
    'SLAVES':           'Slavery',
}

items = {
    'ALLOYS': DELETED,
    'CENTAURI MEGA GIN': DELETED,
    'CONSUMER TECH': 'Consumer Technology',
    'COTTON': DELETED,
    'DOM. APPLIANCES': 'Domestic Appliances',
    'FRUIT AND VEGETABLES': 'Fruit And Vegetables',
    'HEL-STATIC FURNACES': 'Microbial Furnaces',
    'HYDROGEN FUELS':   'Hydrogen Fuel',
    'MARINE SUPPLIES':  'Marine Equipment',
    'NON-LETHAL WPNS': 'Non-Lethal Weapons',
    'PLASTICS': DELETED,
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

