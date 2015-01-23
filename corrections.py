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
    "54 G. ANTLIA/BOAS ORBITAL":            DELETED,
    "61 URSAE MAJORIS/WORLIDGE DOCK":       DELETED,
    "70 VIRGINIS/REIS PLATFORM":            DELETED,
    "ADENETS/ALLEN HORIZONS":               DELETED,
    "ADEO/OOBROVOLSKI CITY":                "Dobrovolski City",
    "AKHENATEN/WANG PLATFORM":              DELETED,
    "AKNANGO/BANKS STATION":                DELETED,
    "AL MINA/DANA PORT":                    DELETED,
    "ALBICEVCI/DUBROVOLSKI SURVEY":         "Dobrovolski Survey",
    "ALKUNDAN/FONTENAY LANOING":            "Fontenay Landing",
    "ALRAI/BOUNDSHUB":                      "Bounds Hub",
    "AMAIT/LOPEZ DE VILLALOBOS":            "Lopez De Villalobos Prospect",
    "AMARAK/WERNER VON SIEMENS VISON":      "Werner Von Siemens Vision",
    "ANAPOS/HERSCHEL PLATFORM":             "Herschel Plant",
    "ANLAVE/KOBAYASHICRY":                  "Kobayashi City",
    "AO QIN/CHAPMAN HUB":                   DELETED,
    "APALA/JONES TERMINAL":                 DELETED,
    "APOYOTA/FLINTSTATION":                 "Flint Station",
    "APOYOTA/HAHNRELAY":                    "Hahn Relay",
    "AULIN/ALUIN ENTERPIRSE":               "Aulin Enterprise",
    "BALDUR/DUTTON STATION":                DELETED,
    "BD+13 693/DRUMMOND`S PROGRESS":        "Drummond's Progress",
    "BD+65 1846/SHARGIN BEACON":            DELETED,
    "BD-02 4304/NEWTON OOCK":               "Newton Dock",
    "BD-02 4304/OURRANCE STATION":          "Durrance Station",
    "BD-17 6172/REEO ORBITAL":              "Reed Orbital",
    "BOLG/MOXONS MOJO":                     "Moxon's Mojo",
    "CEMIESS/TITUS STATION":                "Titius Station",
    "CHACOCHA/OINEILL SETTLEMENT":          "O'Neill Settlement",
    "COCKAIGNE/OTTLEYS LANDING":            "Ottley's Landing",
    "DORIS/ISHERWOOD DOCK":                 DELETED,
    "DT VIRGINIS/CHUN STATION":             "Chun Vision",
    "DUAMTA/GERNSBACK TERMINAL":            DELETED,
    "EGOVAE/ENOATE MARKET":                 "Endate Market",
    "EKONIR/MOREYVISION":                   "Morey Vision",
    "ERAVATE/ASKERMAN MARKET":              "Ackerman Market",
    "ERAVATE/RUSSEL RING":                  "Russell Ring",
    "EURYBIA/CHRIS & SILVIA''S PARADISE HIDEOUT":   "Chris & Silvia's Paradise Hideout",
    "EURYBIA/CHRIS & SILVIA''S PARADISE HIDEOUT":   "Chris & Silvia's Paradise Hideout",
    "FROG/KEMPSTON HAROWICK":               "Kempston Hardwick",
    "G 123-49/JET-GANG":                    DELETED,
    "G 139-50/FILIPCHENKO":                 "Filipchenko City",
    "GCRV 4654/HERZEFELD LANDING":          "Herzfeld Landing",
    "GEORGE PANTAZIS/ZAKAM PLATFORM":       "Zamka Platform",
    "GRANTHAIMI/PARMITANO":                 "Parmitano Colony",
    "GROOMBRIDGE 1618/FRANKUN RING":        "Franklin Ring",
    "HACH/(EVANS CITY)":                    "Evans City",
    "HALAI/GENKER STATION":                 "Cenker Station",
    "HARED/MOREY REFINARY":                 "Morey Refinery",
    "HDS 1879/HEDIN ORBITAL":               DELETED,
    "HIP 110483/VALIGURSKY ORBITAE":        "Valigursky Orbital",
    "HIP 4907/EDISON PLATFORM":             DELETED,
    "HO HSIEN/OUTTON STATION":              "Dutton Station",
    "HR 1257/MILLAR SETTLEMENT":            "Miller Settlement",
    "HR 5451/MACDONALO HUB":                "MacDonald Hub",
    "HR 5451/MACOONALD HUB":                "MacDonald Hub",
    "HR 5451/MACOONALO HUB":                "MacDonald Hub",
    "JAWOLA/SUTCLIFFEPLATFORM":             "Sutcliffe Platform",
    "JERA/MOOREDOCK":                       "Moore Dock",
    "KANOS/LEE STATION":                    DELETED,
    "LAIFAN/CHILTON OOCK":                  "Chilton Dock",
    "LEESTI/GEORGELUCAS":                   "George Lucas",
    "LFT 1446/BOSCH SETTLEMENT":            DELETED,
    "LFT 926/MEREDITH STATION":             "Meredith City",
    "LHS 1065/HORNBLOWER PLATFORM":         DELETED,
    "LHS 1101/BONDAR CITY":                 DELETED,
    "LHS 220/CULPEPERCOLONY":               "Culpeper Colony",
    "LHS 2363/KENNAN PLATFORM":             DELETED,
    "LHS 250/KOVALESKY ENTERPRISE":         "Kovalevsky Enterprise",
    "LHS 2651/BERGERAC RING":               DELETED,
    "LHS 2651/SCHMITZ GATEWAY":             DELETED,
    "LHS 2651/SHIPTON ORBITAL":             DELETED,
    "LHS 2884/ABNETT PLATEFORM":            "Abnett Platform",
    "LHS 331/HOPKINSON CITY":               DELETED,
    "LHS 3447/0ALTON GATEWAY":              "Dalton Gateway",
    "LHS 64/WIBERG HANGAR":                 "Wiberg Hanger",
    "LP 254-40/JACOBIDOCK":                 "Jacobi Dock",
    "LP 254-40/JACOBIOOCK":                 "Jacobi Dock",
    "LP 322-836/BOLOTOV PORT":              DELETED,
    "LP 51-17/ARCHAMBAULT HORIZONS":        DELETED,
    "LP 811-17/STJEPAN SELJAN PORT":        DELETED,
    "LP 862-184/MAYR HANGAR":               "Mayr Hanger",
    "LTT 15449/REILLI DOCK":                "Reilly Dock",
    "LTT 16218/CHARGAFFPORT":               "Chargaff Port",
    "LTT 16523/IVINS MAKRET":               "Ivins Market",
    "LTT 4150/BRADY COLONY'":               "Brady Colony",
    "LTT 7548/ALEXANDRIA RINF":             "Alexandria Ring",
    "LTT 9455/OLEARY VISION":               "O'Leary Vision",
    "LTT 9663/BRAOLEY SURVEY":              "Bradley Survey",
    "MANNODAVA/ALIPORT":                    "Ali Port",
    "MANNONA/THORNYCROFY PENAL COLONY":     "Thornycroft Penal Colony",
    "MCC 467/ROB HUBBARD RING":             "Ron Hubbard Ring",
    "MINJANGO/OENNING PLATFORM":            "Denning Platform",
    "MISISTURE/GELFANO DOCK":               "Gelfand Dock",
    "MISISTURE/GELFANO OOCK":               "Gelfand Dock",
    "MOKOSH/LUBEN ORBITAL":                 "Lubin Orbital",
    "NLTT 49528/OCONNORLANQNG":             "O'Connor Landing",
    "NLTT 49528/O‹CONNOR LANDING":        "O'Connor Landing",
    "OCSHODHIS/LLOYD OOCK":                 "Lloyd Dock",
    "ONGKAMPAN/PATTERSON STATION:274":      "Patterson Station",
    "OPALA/ZAMK PLATFORM":                  "Zamka Platform",
    "ORERVE/WATSON SATION":                 "Watson Station",
    "PANGLUYA/BRADBURYWORKS":               "Bradbury Works",
    "PERENDI/SHEPHERD INSTALLATION":        DELETED,
    "PI PISCIS AUSTRINI/FARGHANIHUB":       "Farghani Hub",
    "PRIVA/DUGAN OOCK":                     "Dugan Dock",
    "PRIVA/OUGAN DOCK":                     "Dugan Dock",
    "PRIVA/OUGAN OOCK":                     "Dugan Dock",
    "RAHU/LEBEDEV BEACON":                  DELETED,
    "RHO CANCRI/HAMILTON R‚SERVE":          "Hamilton Reserve",
    "RHO CANCRI/HAMILTON R�SERVE":          "Hamilton Reserve",
    "SAMEN/PETERS TERMINAL PAD=L LS=240":   "Peters Terminal",
    "SHEELA NA GIG/BIRKHOFF TERMINAL":      DELETED,
    "STEIN 2051/TREVITHICK PORT":           DELETED,
    "TAHA DERG/0URRANCE LANDING":           "Durrance Landing",
    "TENG YEH/GARAN SURVERY":               "Garan Survey",
    "TIETHAY/SANTOS PLANT1":                DELETED,
    "TJURINAS/HERNOON OOCK":                "Herndon Dock",
    "TRELLA/TITTO COLONY":                  "Tito Colony",
    "TSIM BINBA/KOPALORBDAL":               "Kopal Orbital",
    "TUAREG/KOPFF OOCK":                    "Kopff Dock",
    "TYR/GLASHOW":                          "Glashow Dock",
    "V774 HERCULIS/MENDEL MINES'":          "Mendel Mines",
    "V774 HERCULIS/MENOEL MINES":           "Mendel Mines",
    "V989 CASSIOPEIAE/LOW WORKS":           DELETED,
    "VALDA/CLAIRAUT OOCK":                  "Clairaut Dock",
    "VEQUESS/AGNEWS FOLLY":                 "Agnews' Folly",
    "WOLF 1301/SAUNDER'S DIVE":             "Saunders's Dive",
    "WOLF 1301/SAUNDERS'S OIVE":            "Saunders's Dive",
    "WOLF 294/STEPHENSON OOCK":             "Stephenson Dock",
    "WOLF 46/FISCHER CITY":                 "Fischer Station",
    "YAB CAMALO/KIOO CITY":                 "Kidd City",
    "YAKABUGAI/SEREBOV STATION":            "Serebrov Station",
    "YAKABUGAI/SEREBROV":                   "Serebrov Station",
    "YANYAN/MORYN CITY":                    "Morin City",
    "YAWA/OEAN HUB":                        "Dean Hub",
    "ZARYA MANAS/ANTONIO OE ANDRADE HUB":   "Antonio de Andrade Hub",
    "ZARYA MANAS/ANTONIO OE ANDRAOE HUB":   "Antonio de Andrade Hub",
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

