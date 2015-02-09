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
    "171 G. AQUARII/ELCANO OOCK":           "Elcano Dock",
    "21 DRACO/ROBERTS PORT":                DELETED,
    "37 XI BOOTIS/SCHIRRA PLANT":           "Schirba Plant",
    "51 AQUILAE/COKEHUB":                   "Coke Hub",
    "ADENETS/ALLEN HORIZONS":               DELETED,
    "ADEO/OOBROVOLSKI CITY":                "Dobrovolski City",
    "AFLI/QU IETELET DOCK":                 DELETED,
    "AINUNNICORI/TANIHUB":                  "Tani Hub",
    "AKANDI/AGNESICOLONY":                  DELETED,
    "AKHENATEN/WANG PLATFORM":              DELETED,
    "ALBICEVCI/DUBROVOLSKI SURVEY":         "Dobrovolski Survey",
    "AMAIT/LOPEZ DE VILLALOBOS":            "Lopez De Villalobos Prospect",
    "AMARAK/WERNER VON SIEMENS VISON":      "Werner Von Siemens Vision",
    "ANAPOS/HERSCHEL PLATFORM":             "Herschel Plant",
    "ANINOHANU/BAROEEN HANGER":             DELETED,
    "ANLAVE/KOBAYASHICRY":                  "Kobayashi City",
    "ANLAVE/SURIPARK" :                     DELETED,
    "ANSUZ/MARCONIHANGER":                  DELETED,
    "AO QIN/CHAPMAN HUB":                   DELETED,
    "APOYOTA/FLINTSTATION":                 "Flint Station",
    "APOYOTA/HAH N RELAY":                  DELETED,
    "APOYOTA/HAHNRELAY":                    "Hahn Relay",
    "ARTEMIS/BURCKHAROT STATION":           DELETED,
    "ASASE YA/OREYER GATEWAY":              DELETED,
    "AULIN/ALUIN ENTERPIRSE":               "Aulin Enterprise",
    "AULIN/EOWAROS RING":                   DELETED,
    "BALDUR/DUTTON STATION":                DELETED,
    "BALTAH'SINE/BALTAH''SINE STATION":     DELETED,
    "BALTAH'SINE/BALTHAISINE STATION":      DELETED,
    "BAVARINGONI/CHAN DLER PLATFORM":       "Chandler Platform",
    "BD+13 693/DRUMMOND`S PROGRESS":        "Drummond's Progress",
    "BD+65 1846/SHARGIN BEACON":            DELETED,
    "BD-02 4304/BRANOENSTEIN ENTERPRISE":   DELETED,
    "BD-02 4304/OURRANCE STATION":          DELETED,
    "BOLG/MOXONS MOJO":                     "Moxon's Mojo",
    "CEMIESS/TITUS STATION":                "Titius Station",
    "COCIJO/HARRY MOORE 6 CO":              DELETED,
    "COSI/JU LIAN CITY":                    "Julian City",
    "CPD-28 332/WI N N E GATEWAY":          DELETED,
    "DAJOAR/MACQUORN TERMINAL":             DELETED,
    "DELTA PAVONIS/BURSCH ENTERPRISE":      DELETED,
    "DELTA PAVONIS/READDY GATEVVAY":        DELETED,
    "DELTA PAVONIS/WARREN PRISON MINE":     DELETED,
    "DITAE/DITAE":                          DELETED,
    "DORIS/ISHERWOOD DOCK":                 DELETED,
    "DT VIRGINIS/CHUN STATION":             "Chun Vision",
    "EGOVAE/ENOATE MARKET":                 "Endate Market",
    "EHECATL/MURDOCK DOCK":                 "Murdoch Dock",
    "EKONIR/MOREYVISION":                   "Morey Vision",
    "ERAVATE/ACKERMAN MAHKET":              "Ackerman Market",
    "ERLIK/REYNOLOS TERMINAL":              DELETED,
    "ETA CASSIOPEIAE/JEKENNEOY":            "J.F.Kennedy",
    "FROG/KEMPSTON HAROWICK":               "Kempston Hardwick",
    "FUTHORC/ACQUIREO TASTE ORBITAL":       DELETED,
    "G 165-13/NAODODOUR PLATFORM":          DELETED,
    "GCRV 4654/HERZEFELD LANDING":          "Herzfeld Landing",
    "GD 219/MCKEF RING":                    DELETED,
    "GD 219/MCKFE RING":                    DELETED,
    "GROOMBRIDGE 1618/FRANKUN RING":        "Franklin Ring",
    "HATMEHING/HEVEI.IUS TERMINAL":         DELETED,
    "HATMEHING/HEVEIIUS TERMINAL":          DELETED,
    "HDS 1879/HEDIN ORBITAL":               DELETED,
    "HILLAUNGES/ARGELANOER PORT":           DELETED,
    "HIP 110483/VALIGURSKY ORBITAE":        "Valigursky Orbital",
    "HIP 4907/EDISON PLATFORM":             DELETED,
    "HIP 69913/KONORATYEV OUTPOST":         DELETED,
    "HR 5451/MACDONALO HUB":                "MacDonald Hub",
    "HR 5451/MACOONALD HUB":                "MacDonald Hub",
    "HR 5451/MACOONALO HUB":                "MacDonald Hub",
    "IX CHAKAN/LEBEOEV ENTERPRISE":         DELETED,
    "JAWOLA/SUTCLIFFEPLATFORM":             "Sutcliffe Platform",
    "KANOS/LEE STATION":                    DELETED,
    "KHOLEDO/LOPEZ DE DILLALOBOS COLONY":   "Lopez De Villalobos Colony",
    "KINI/Kadenyuk":                        "Kadenyuk Orbital",
    "KINI/Kaoenyuk Orbital":                "Kadenyuk Orbital",
    "LALANDE 39866/GODDARO CITY":           DELETED,
    "LALANDE 39866/GOODARD CITY":           DELETED,
    "LEESTI/GEORGELUCAS":                   "George Lucas",
    "LFT 1446/BOSCH SETTLEMENT":            DELETED,
    "LHS 1101/BONDAR CITY":                 DELETED,
    "LHS 1453/SAAVEORA PORT":               DELETED,
    "LHS 220/CULPEPERCOLONY":               "Culpeper Colony",
    "LHS 2233/GAGNANORBITAL":               DELETED,
    "LHS 250/KOVALESKY ENTERPRISE":         "Kovalevsky Enterprise",
    "LHS 2884/ABNETT PLATEFORM":            "Abnett Platform",
    "LHS 3447/WORLIOGE TERMINAL":           DELETED,
    "LHS 380/QURESHIORBRAL":                DELETED,
    "LHS 53/OCONNOR SETTLEMENT":            "O'Connor Settlement",
    "LHS 64/WIBERG HANGAR":                 "Wiberg Hanger",    # "Hanger",
    "LOVEDU/OIVIS PLATFORM":                DELETED,
    "LP 254-40/JACOBIDOCK":                 DELETED,
    "LP 322-836/BOLOTOV PORT":              DELETED,
    "LP 51-17/ARCHAMBAULT HORIZONS":        DELETED,
    "LP 811-17/STJEPAN SELJAN PORT":        DELETED,
    "LP 862-184/MAYR HANGAR":               "Mayr Hanger",
    "LTT 1349/IIINDWAII CITY":              DELETED,
    "LTT 1349/NORIFRA PORT":                DELETED,
    "LTT 14019/BALLARO GATEWAY":            DELETED,
    "LTT 14437/BRIOGER BASE":               DELETED,
    "LTT 15449/REILLI DOCK":                "Reilly Dock",
    "LTT 16218/CHARGAFFPORT":               "Chargaff Port",
    "LTT 7548/ALEXANDRIA RINF":             "Alexandria Ring",
    "LTT 8750/OUMONT STATION":              DELETED,
    "LTT 9455/OLEARY VISION":               "O'Leary Vision",
    "LUGH/BALANOIN GATEWAY":                DELETED,
    "LUSHERTHA/OE CAMINHA STATION":         "De Caminha Station",
    "MANNODAVA/ALIPORT":                    DELETED,
    "MANNONA/THORNYCROFY PENAL COLONY":     "Thornycroft Penal Colony",
    "MATLEHI/KUBEEMCDOWELL PORT":           "Kube-McDowell Port",
    "MCC 467/ROB HUBBARD RING":             "Ron Hubbard Ring",
    "MINJANGO/OENNING PLATFORM":            "Denning Platform",
    "MISISTURE/GELFANO DOCK":               DELETED,
    "MOKOSH/LUBEN ORBITAL":                 "Lubin Orbital",
    "MORANA/FERRER COLONY":                 "Farrer Colony",
    "NARASIMHA/MENOEL SURVEY":              DELETED,
    "NLTT 49528/OCONNORLANQNG":             "O'Connor Landing",
    "NLTT 49528/O‹CONNOR LANDING":          "O'Connor Landing",
    "NUAKEA/Obuwon":                        "Oblivion",
    "OCHOENG/Rodoenberry":                  "Roddenberry Gateway",
    "OLWAIN/CABOT H U B":                   DELETED,
    "OLWAIN/J. G. BALLARD TERMINAL":        DELETED,
    "ONGKAMPAN/PATTERSON STATION:           274": "Patterson Station",
    "OPALA/ZAMK PLATFORM":                  "Zamka Platform",
    "ORERVE/WATSON SATION":                 "Watson Station",
    "OSSITO/STOART MINES":                  DELETED,
    "PAND/SARMIENTO OE GAMBOA PORT":        "Sarmiento de Gamboa Port",
    "PANGLUYA/BRADBURYWORKS":               "Bradbury Works",
    "PERENDI/SHEPHERD INSTALLATION":        DELETED,
    "PHRYGIA/OEN BERG HUB":                 DELETED,
    "PRIVA/DUGAN OOCK":                     "Dugan Dock",
    "PRIVA/OUGAN DOCK":                     "Dugan Dock",
    "PRIVA/OUGAN OOCK":                     "Dugan Dock",
    "RAHU/LEBEDEV BEACON":                  DELETED,
    "RATHAMAS/ARTZYBASHEFF H U B":          DELETED,
    "RIEDQUAT/LA SOEUR OU DAN HAM":         "La Soeur du Dan Ham",
    "RHO CANCRI/HAMILTON R,SERVE":          "Hamilton Reserve",
    "RHO CANCRI/HAMILTON R�SERVE":          "Hamilton Reserve",
    "ROSS 705/EJETY CITY":                  "Ejeta City",
    "ROSS 733/STREDLOV GATEWAY":            "Strekalov Gateway",
    "ROSS 733/STRERLOV GATEWAY":            "Strekalov Gateway",
    "ROSS 754/OANA GATEWAY":                "Dana Gateway",
    "SAMBURITJA/.PTEYN LANDING":            "Kapteyn Landing",
    "SAMBURITJA/PTEYN LANDING":             "Kapteyn Landing",
    "SITLANEI/VON BELLINGSHAAUSEN ORBITAL": "von Bellingshausen Orbital",
    "SORBAGO/CARROLLSURVEY":                DELETED,
    "SRS 2543/0IRAC TERMINAL":              DELETED,
    "STEIN 2051/TREVITHICK PORT":           DELETED,
    "TAHA DERG/0URRANCE LANDING":           DELETED,
    "TANMARK/CASSI E-L-PEIA":               DELETED,
    "TARACH TOR/TRANQUEUTY":                DELETED,
    "TARACH TOR/TRANQUNLRY":                DELETED,
    "TARACH TOR/TRANQUWUTY":                DELETED,
    "TENG YEH/GARAN SURVERY":               "Garan Survey",
    "THUNDERBIRD/QUIMPY PORT":              DELETED,
    "TIETHAY/SANTOS PLANT1":                DELETED,
    "TRELLA/TITTO COLONY":                  "Tito Colony",
    "TSIM BINBA/KO PAL ORBITAL":            "Kopal Orbital",
    "TSIM BINBA/KOPAL ORBRAL":              "Kopal Orbital",
    "TSOHODA/OE LAY PORT":                  "De Lay Port",
    "TUAREG/KOPFF OOCK":                    "Kopff Dock",
    "TURMO/VANCOUVERSINHERHANCE":           DELETED,
    "TYR/GLASHOW":                          "Glashow Dock",
    "USZAA/GUEST INSTAL'ION":               DELETED,
    "USZAA/GUEST INSTALQTION":              DELETED,
    "V2213 OPHIUCHII/OE ANDRADE DOCK":      "De Andrade Dock",
    "V774 HERCULIS/MENDEL MINES'":          "Mendel Mines",
    "V774 HERCULIS/MENOEL MINES":           "Mendel Mines",
    "V989 CASSIOPEIAE/LOW WORKS":           DELETED,
    "VALDA/CLAIRAUT OOCK":                  "Clairaut Dock",
    "VEQUESS/AGNEWS FOLLY":                 "Agnews' Folly",
    "VERBIGENI/ARCHAMBAU ILT PLANT":        "Archambault Plant",
    "VEROANDI/VAROEMAN GATEWAY":            DELETED,
    "WADJALI/KIOMAN TERMINAL":              DELETED,
    "WOLF 1301/SAUNDER'S DIVE":             "Saunders's Dive",
    "WOLF 1409/ZAMR TERMINAL":              "Zamka Terminal",
    "WOLF 46/FISCHER CITY":                 "Fischer Station",
    "WOLF 424/SPING TERMINAL":              DELETED,
    "WOLF 424/SPRING TERMINAL":             DELETED,
    "WOLF 629/GRUNSFIELD PLANT":            "Grunsfeld Plant",
    "WW PISCIS AUSTRINI/INVINS VISION":     DELETED,
    "WW PISCIS AUSTRINI/IVINR VISION":      DELETED,
    "YAKABUGAI/SEREBOV STATION":            "Serebrov Station",
    "YAKABUGAI/SEREBROV":                   "Serebrov Station",
    "YANYAN/MORYN CITY":                    "Morin City",
    "YAWA/OEAN HUB":                        DELETED,
    "YORUBA/CARPENTERS TERMINAL":           "Carpenter Terminal",
    "ZETA AQUILAE/JULIAN GATEWAY":          DELETED,
    "ZETA AQUILAE/MOHMAND HOLOINGS":        "Mohmand Holdings",
    "ZETA AQUILAE/MOHMANO HOLDINGS":        "Mohmand Holdings",
    "ZETA AQUILAE/OEFELIEN":                "Oefelein Plant",
    "ZETA TRIANGULI AUSTRALIS/GUEST CITY2": "Guest City",

#ADD_STATIONS_HERE
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

