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
	"ANINOHANU/BAROEEN HANGER":             DELETED,
	"ANLAVE/SURIPARK" :                     DELETED,
	"ARTEMIS/BURCKHAROT STATION":           DELETED,
	"BD-02 4304/BRANOENSTEIN ENTERPRISE":	DELETED,
	"ERLIK/REYNOLOS TERMINAL":              DELETED,
	"FUTHORC/ACQUIREO TASTE ORBITAL":       DELETED,
	"G 165-13/NAODODOUR PLATFORM":          DELETED,
	"HATMEHING/HEVEI.IUS TERMINAL":         DELETED,
	"HATMEHING/HEVEIIUS TERMINAL":          DELETED,
	"HIP 69913/KONORATYEV OUTPOST":         DELETED,
	"LHS 1453/SAAVEORA PORT":               DELETED,
	"LHS 3447/WORLIOGE TERMINAL":           DELETED,
	"LUGH/BALANOIN GATEWAY":                DELETED,
	"NARASIMHA/MENOEL SURVEY":              DELETED,
	"OSSITO/STOART MINES":                  DELETED,
	"SORBAGO/CARROLLSURVEY":                DELETED,
	"THUNDERBIRD/QUIMPY PORT":	            DELETED,
	"VEROANDI/VAROEMAN GATEWAY":	        DELETED,
    "171 G. AQUARII/ELCANO OOCK":           "Elcano Dock",
    "21 DRACO/ROBERTS PORT":                DELETED,
    "37 XI BOOTIS/SCHIRRA PLANT":           "Schirba Plant",
    "51 AQUILAE/COKEHUB":                   "Coke Hub",
    "ADENETS/ALLEN HORIZONS":               DELETED,
    "ADEO/OOBROVOLSKI CITY":                "Dobrovolski City",
    "AINUNNICORI/TANIHUB":                  "Tani Hub",
    "AKANDI/AGNESICOLONY":                  DELETED,
    "AKHENATEN/WANG PLATFORM":              DELETED,
    "ALBICEVCI/DUBROVOLSKI SURVEY":         "Dobrovolski Survey",
    "AMAIT/LOPEZ DE VILLALOBOS":            "Lopez De Villalobos Prospect",
    "AMARAK/WERNER VON SIEMENS VISON":      "Werner Von Siemens Vision",
    "ANAPOS/HERSCHEL PLATFORM":             "Herschel Plant",
    "ANLAVE/KOBAYASHICRY":                  "Kobayashi City",
    "AO QIN/CHAPMAN HUB":                   DELETED,
    "APOYOTA/FLINTSTATION":                 "Flint Station",
    "APOYOTA/HAHNRELAY":                    "Hahn Relay",
    "AULIN/ALUIN ENTERPIRSE":               "Aulin Enterprise",
    "BALDUR/DUTTON STATION":                DELETED,
    "BD+13 693/DRUMMOND`S PROGRESS":        "Drummond's Progress",
    "BD+65 1846/SHARGIN BEACON":            DELETED,
    "BD-02 4304/OURRANCE STATION":          DELETED,
    "BOLG/MOXONS MOJO":                     "Moxon's Mojo",
    "CEMIESS/TITUS STATION":                "Titius Station",
    "DORIS/ISHERWOOD DOCK":                 DELETED,
    "DT VIRGINIS/CHUN STATION":             "Chun Vision",
    "EGOVAE/ENOATE MARKET":                 "Endate Market",
    "EKONIR/MOREYVISION":                   "Morey Vision",
    "FROG/KEMPSTON HAROWICK":               "KempstoN Hardwick",
    "GCRV 4654/HERZEFELD LANDING":          "Herzfeld Landing",
    "GROOMBRIDGE 1618/FRANKUN RING":        "Franklin Ring",
    "HDS 1879/HEDIN ORBITAL":               DELETED,
    "HIP 110483/VALIGURSKY ORBITAE":        "Valigursky Orbital",
    "HIP 4907/EDISON PLATFORM":             DELETED,
    "HR 5451/MACDONALO HUB":                "MacDonald Hub",
    "HR 5451/MACOONALD HUB":                "MacDonald Hub",
    "HR 5451/MACOONALO HUB":                "MacDonald Hub",
    "JAWOLA/SUTCLIFFEPLATFORM":             "Sutcliffe Platform",
    "KANOS/LEE STATION":                    DELETED,
    "LEESTI/GEORGELUCAS":                   "George Lucas",
    "LFT 1446/BOSCH SETTLEMENT":            DELETED,
    "LHS 1101/BONDAR CITY":                 DELETED,
    "LHS 220/CULPEPERCOLONY":               "Culpeper Colony",
    "LHS 250/KOVALESKY ENTERPRISE":         "Kovalevsky Enterprise",
    "LHS 2884/ABNETT PLATEFORM":            "Abnett Platform",
    "LHS 64/WIBERG HANGAR":                 "Wiberg Hanger",    # "Hanger",
    "LP 254-40/JACOBIOOCK":                 "Jacobi Dock",
    "LP 322-836/BOLOTOV PORT":              DELETED,
    "LP 51-17/ARCHAMBAULT HORIZONS":        DELETED,
    "LP 811-17/STJEPAN SELJAN PORT":        DELETED,
    "LP 862-184/MAYR HANGAR":               "Mayr Hanger",
    "LTT 15449/REILLI DOCK":                "Reilly Dock",
    "LTT 16218/CHARGAFFPORT":               "Chargaff Port",
    "LTT 7548/ALEXANDRIA RINF":             "Alexandria Ring",
    "LTT 9455/OLEARY VISION":               "O'Leary Vision",
    "MANNODAVA/ALIPORT":                    DELETED,
    "MANNONA/THORNYCROFY PENAL COLONY":     "Thornycroft Penal Colony",
    "MCC 467/ROB HUBBARD RING":             "Ron Hubbard Ring",
    "MINJANGO/OENNING PLATFORM":            "Denning Platform",
    "MISISTURE/GELFANO DOCK":               DELETED,
    "MOKOSH/LUBEN ORBITAL":                 "Lubin Orbital",
    "NLTT 49528/OCONNORLANQNG":             "O'Connor Landing",
    "NLTT 49528/O‹CONNOR LANDING":        "O'Connor Landing",
    "ONGKAMPAN/PATTERSON STATION:           274": "Patterson Station",
    "OPALA/ZAMK PLATFORM":                  "Zamka Platform",
    "ORERVE/WATSON SATION":                 "Watson Station",
    "PANGLUYA/BRADBURYWORKS":               "Bradbury Works",
    "PERENDI/SHEPHERD INSTALLATION":        DELETED,
    "PRIVA/DUGAN OOCK":                     "Dugan Dock",
    "PRIVA/OUGAN DOCK":                     "Dugan Dock",
    "PRIVA/OUGAN OOCK":                     "Dugan Dock",
    "RAHU/LEBEDEV BEACON":                  DELETED,
    "RHO CANCRI/HAMILTON R,SERVE":          "Hamilton Reserve",
    "RHO CANCRI/HAMILTON R�SERVE":        "Hamilton Reserve",
    "STEIN 2051/TREVITHICK PORT":           DELETED,
    "TAHA DERG/0URRANCE LANDING":           DELETED,
    "TANMARK/CASSI E-L-PEIA":               DELETED,
    "TARACH TOR/TRANQUEUTY":                DELETED,
    "TARACH TOR/TRANQUNLRY":                DELETED,
    "TARACH TOR/TRANQUWUTY":                DELETED,
    "TENG YEH/GARAN SURVERY":               "Garan Survey",
    "TIETHAY/SANTOS PLANT1":                DELETED,
    "TRELLA/TITTO COLONY":                  "Tito Colony",
    "TUAREG/KOPFF OOCK":                    "Kopff Dock",
    "TURMO/VANCOUVERSINHERHANCE":           DELETED,
    "TYR/GLASHOW":                          "Glashow Dock",
    "V774 HERCULIS/MENDEL MINES'":          "Mendel Mines",
    "V774 HERCULIS/MENOEL MINES":           "Mendel Mines",
    "V989 CASSIOPEIAE/LOW WORKS":           DELETED,
    "VALDA/CLAIRAUT OOCK":                  "Clairaut Dock",
    "VEQUESS/AGNEWS FOLLY":                 "Agnews' Folly",
    "WOLF 1301/SAUNDER'S DIVE":             "Saunders's Dive",
    "WOLF 46/FISCHER CITY":                 "Fischer Station",
    "YAKABUGAI/SEREBOV STATION":            "Serebrov Station",
    "YAKABUGAI/SEREBROV":                   "Serebrov Station",
    "YANYAN/MORYN CITY":                    "Morin City",
    "YAWA/OEAN HUB":                        DELETED,
    "ZETA AQUILAE/JULIAN GATEWAY":          DELETED,
    "ZETA AQUILAE/OEFELIEN":                "Oefelein Plant",
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

