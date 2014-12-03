# Provides an interface for correcting star/station names that
# have changed in recent versions.

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

# Arbitrary, negative value to denote something that's been removed.
DELETED = -111

systems = {
    "LTT 4549": "Shinrarta Dezhra",
    "KAMCHAULTULTULA": "Aiabiko",

    # Gamma 1
    "ACURUKUNABOGAMAL": "Temba",
    "ADITYARAGUALA": "Lushertha",
    "ALADU KUAN GON": "Undadja",
    "AUDHISATSURI": "Esuseku",
    "BEGOU": "Cephei Sector FG-Y c30",
    "BOROM CAQUIT": "Hual",
    "BURYACUAN WU": "Katta",
    "CARNUTENICHUARA": "Het",
    "CEPHEI SECTOR IR-W C1-17": "Awawad",
    "CEPHEI SECTOR JC-V B2-4": "Kavalan",
    "CEPHEI SECTOR TO-R B4-3": "Jieguaje",
    "CM DRACO": "CM Draconis",
    "CORIOSKEH TRYTH": "Brid",
    "DAKANTJARINI": "Chapo",
    "EGOVEDUNUVITRA": "Kondovii",
    "ENUMCLAWILYA": "Potiguara",
    "ETZNABIHIK MANGK": "Puskabui",
    "HARIBALUAYAI": "Lei Manako",
    "JEIDRUNGARAGOTOTO": "Yan Yi",
    "JUATHAO THEELA": "Machadan",
    "KHONG QIN GU": "Coqui Renes",
    "KOKOBUJUNDJI": "Teliu Yuan",
    "KUNAPALANEZTI": "Karbudji",
    "KURUNMINDJUK": "Evejitaense",
    "KUSHENTINONI": "Mehua",
    "KWAKAMITREYJA": "Igala",
    "KWAMENNERO KOJIN": "Carnsan",
    "LAS XENANGARESTI": "Ngaislan",
    "LATUCAIRHEMAIABI": "Suhte",
    "LENG WANJADIMURU": "Dilwa",
    "LOPU MAID FO": "Nebtete",
    "LUGIEN CHABTANI": "Andere",
    "MACOMANELENG MU": "Ubere",
    "MANBAI CHAC MOCO": "Phra Lak",
    "MARANARINJHIAN HSI": "Banisas",
    "MARAUPOL BUMBIN": "Telie",
    "MBUTHAMOVITES": "Hajangerni",
    "MILDJARAYUTA": "Blenu",
    "MOSCAB KUTJA": "Basus",
    "MUANGO": "Cephei Sector NI-T b3-2",
    "NAGARIGGAM": "Kamici",
    "NGOLOKI ANATEN": "Xibe",
    "SKOKOLOCHOERI": "Goplatrugba",
    "SONG TE TIANS": "Moroecani",
    "SUKUB TUNGATIS": "Adenets",
    "T'ANG BUMBAIN": "Gommara",
    "TAEXALKOLOINE": "Queche",
    "TAIMA BAIJUHACMOORA": "Payayan",
    "TALEACHISHVAKHRUD": "Suttonenses",
    "THOSIM BIAMH": "Apala",
    "THOTTACAHUAN WANG": "Shoujeman",
    "WAKARENDIANS": "Susama",
    "WEN TSAKIMORI": "Chielas",
    "YA'NOMISIYACES": "Wong Ten",
    "YERU BAO HINU": "Opones",
    "YUGGSANAWYDDIS": "Kumata",
    "YUGUSITANITOU": "Kulungan",
    "ZOMBARDGRITI": "Tiguai",

#ADD_SYSTEMS_HERE
}

stations = {
    "CHEMAKU/BARTOE PLATFORM": DELETED,

#ADD_STATIONS_HERE
}

categories = {
    'DRUGS':            'Legal Drugs',
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
        pass
    try:
        return stations[oldName.upper()]
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

