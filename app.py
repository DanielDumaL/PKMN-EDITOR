"""
Pokemon PC Box Viewer - con Claude API
========================================
Estrategia: 
  1. Leer el save en bytes
  2. Escanear todos los bloques de 136 bytes buscando PK4 validos
  3. Para los que no se pueden desencriptar bien, usar Claude API
     para identificar species_id y datos clave
  4. Devolver al frontend los Pokemon encontrados organizados en cajas
"""

from flask import Flask, request, jsonify, send_from_directory
import struct, json, re

app = Flask(__name__, static_folder=".")

# ============================================================
# CONSTANTES
# ============================================================
SLOTS_PER_BOX = 30
POKEMON_SIZE  = 136
BOX_SIZE      = SLOTS_PER_BOX * POKEMON_SIZE  # 4080

GAME_OFFSETS = {
    "platinum":     {"storage": 0x0CF2C, "trainer_name": 0x00068, "trainer_id": 0x0007A, "box_names": 0x11F28, "boxes": 18},
    "diamond_pearl":{"storage": 0x0A000, "trainer_name": 0x00064, "trainer_id": 0x00074, "box_names": 0x0DA40, "boxes": 18},
    "hgss":         {"storage": 0x0F700, "trainer_name": 0x00064, "trainer_id": 0x00074, "box_names": 0x12580, "boxes": 18},
    "firered":      {"storage": 0x05524, "trainer_name": 0x00000, "trainer_id": 0x0000A, "box_names": None,    "boxes": 14},
    "emerald":      {"storage": 0x0D900, "trainer_name": 0x00000, "trainer_id": 0x0000A, "box_names": None,    "boxes": 14},
}

POKEMON_NAMES = {
    0:"???",1:"Bulbasaur",2:"Ivysaur",3:"Venusaur",4:"Charmander",5:"Charmeleon",
    6:"Charizard",7:"Squirtle",8:"Wartortle",9:"Blastoise",10:"Caterpie",11:"Metapod",
    12:"Butterfree",13:"Weedle",14:"Kakuna",15:"Beedrill",16:"Pidgey",17:"Pidgeotto",
    18:"Pidgeot",19:"Rattata",20:"Raticate",21:"Spearow",22:"Fearow",23:"Ekans",
    24:"Arbok",25:"Pikachu",26:"Raichu",27:"Sandshrew",28:"Sandslash",29:"Nidoran♀",
    30:"Nidorina",31:"Nidoqueen",32:"Nidoran♂",33:"Nidorino",34:"Nidoking",
    35:"Clefairy",36:"Clefable",37:"Vulpix",38:"Ninetales",39:"Jigglypuff",
    40:"Wigglytuff",41:"Zubat",42:"Golbat",43:"Oddish",44:"Gloom",45:"Vileplume",
    46:"Paras",47:"Parasect",48:"Venonat",49:"Venomoth",50:"Diglett",51:"Dugtrio",
    52:"Meowth",53:"Persian",54:"Psyduck",55:"Golduck",56:"Mankey",57:"Primeape",
    58:"Growlithe",59:"Arcanine",60:"Poliwag",61:"Poliwhirl",62:"Poliwrath",
    63:"Abra",64:"Kadabra",65:"Alakazam",66:"Machop",67:"Machoke",68:"Machamp",
    69:"Bellsprout",70:"Weepinbell",71:"Victreebel",72:"Tentacool",73:"Tentacruel",
    74:"Geodude",75:"Graveler",76:"Golem",77:"Ponyta",78:"Rapidash",79:"Slowpoke",
    80:"Slowbro",81:"Magnemite",82:"Magneton",83:"Farfetch'd",84:"Doduo",85:"Dodrio",
    86:"Seel",87:"Dewgong",88:"Grimer",89:"Muk",90:"Shellder",91:"Cloyster",
    92:"Gastly",93:"Haunter",94:"Gengar",95:"Onix",96:"Drowzee",97:"Hypno",
    98:"Krabby",99:"Kingler",100:"Voltorb",101:"Electrode",102:"Exeggcute",
    103:"Exeggutor",104:"Cubone",105:"Marowak",106:"Hitmonlee",107:"Hitmonchan",
    108:"Lickitung",109:"Koffing",110:"Weezing",111:"Rhyhorn",112:"Rhydon",
    113:"Chansey",114:"Tangela",115:"Kangaskhan",116:"Horsea",117:"Seadra",
    118:"Goldeen",119:"Seaking",120:"Staryu",121:"Starmie",122:"Mr. Mime",
    123:"Scyther",124:"Jynx",125:"Electabuzz",126:"Magmar",127:"Pinsir",
    128:"Tauros",129:"Magikarp",130:"Gyarados",131:"Lapras",132:"Ditto",
    133:"Eevee",134:"Vaporeon",135:"Jolteon",136:"Flareon",137:"Porygon",
    138:"Omanyte",139:"Omastar",140:"Kabuto",141:"Kabutops",142:"Aerodactyl",
    143:"Snorlax",144:"Articuno",145:"Zapdos",146:"Moltres",147:"Dratini",
    148:"Dragonair",149:"Dragonite",150:"Mewtwo",151:"Mew",
    152:"Chikorita",153:"Bayleef",154:"Meganium",155:"Cyndaquil",156:"Quilava",
    157:"Typhlosion",158:"Totodile",159:"Croconaw",160:"Feraligatr",161:"Sentret",
    162:"Furret",163:"Hoothoot",164:"Noctowl",165:"Ledyba",166:"Ledian",
    167:"Spinarak",168:"Ariados",169:"Crobat",170:"Chinchou",171:"Lanturn",
    172:"Pichu",173:"Cleffa",174:"Igglybuff",175:"Togepi",176:"Togetic",
    177:"Natu",178:"Xatu",179:"Mareep",180:"Flaaffy",181:"Ampharos",
    182:"Bellossom",183:"Marill",184:"Azumarill",185:"Sudowoodo",186:"Politoed",
    187:"Hoppip",188:"Skiploom",189:"Jumpluff",190:"Aipom",191:"Sunkern",
    192:"Sunflora",193:"Yanma",194:"Wooper",195:"Quagsire",196:"Espeon",
    197:"Umbreon",198:"Murkrow",199:"Slowking",200:"Misdreavus",201:"Unown",
    202:"Wobbuffet",203:"Girafarig",204:"Pineco",205:"Forretress",206:"Dunsparce",
    207:"Gligar",208:"Steelix",209:"Snubbull",210:"Granbull",211:"Qwilfish",
    212:"Scizor",213:"Shuckle",214:"Heracross",215:"Sneasel",216:"Teddiursa",
    217:"Ursaring",218:"Slugma",219:"Magcargo",220:"Swinub",221:"Piloswine",
    222:"Corsola",223:"Remoraid",224:"Octillery",225:"Delibird",226:"Mantine",
    227:"Skarmory",228:"Houndour",229:"Houndoom",230:"Kingdra",231:"Phanpy",
    232:"Donphan",233:"Porygon2",234:"Stantler",235:"Smeargle",236:"Tyrogue",
    237:"Hitmontop",238:"Smoochum",239:"Elekid",240:"Magby",241:"Miltank",
    242:"Blissey",243:"Raikou",244:"Entei",245:"Suicune",246:"Larvitar",
    247:"Pupitar",248:"Tyranitar",249:"Lugia",250:"Ho-Oh",251:"Celebi",
    252:"Treecko",253:"Grovyle",254:"Sceptile",255:"Torchic",256:"Combusken",
    257:"Blaziken",258:"Mudkip",259:"Marshtomp",260:"Swampert",261:"Poochyena",
    262:"Mightyena",263:"Zigzagoon",264:"Linoone",265:"Wurmple",266:"Silcoon",
    267:"Beautifly",268:"Cascoon",269:"Dustox",270:"Lotad",271:"Lombre",
    272:"Ludicolo",273:"Seedot",274:"Nuzleaf",275:"Shiftry",276:"Taillow",
    277:"Swellow",278:"Wingull",279:"Pelipper",280:"Ralts",281:"Kirlia",
    282:"Gardevoir",283:"Surskit",284:"Masquerain",285:"Shroomish",286:"Breloom",
    287:"Slakoth",288:"Vigoroth",289:"Slaking",290:"Nincada",291:"Ninjask",
    292:"Shedinja",293:"Whismur",294:"Loudred",295:"Exploud",296:"Makuhita",
    297:"Hariyama",298:"Azurill",299:"Nosepass",300:"Skitty",301:"Delcatty",
    302:"Sableye",303:"Mawile",304:"Aron",305:"Lairon",306:"Aggron",
    307:"Meditite",308:"Medicham",309:"Electrike",310:"Manectric",311:"Plusle",
    312:"Minun",313:"Volbeat",314:"Illumise",315:"Roselia",316:"Gulpin",
    317:"Swalot",318:"Carvanha",319:"Sharpedo",320:"Wailmer",321:"Wailord",
    322:"Numel",323:"Camerupt",324:"Torkoal",325:"Spoink",326:"Grumpig",
    327:"Spinda",328:"Trapinch",329:"Vibrava",330:"Flygon",331:"Cacnea",
    332:"Cacturne",333:"Swablu",334:"Altaria",335:"Zangoose",336:"Seviper",
    337:"Lunatone",338:"Solrock",339:"Barboach",340:"Whiscash",341:"Corphish",
    342:"Crawdaunt",343:"Baltoy",344:"Claydol",345:"Lileep",346:"Cradily",
    347:"Anorith",348:"Armaldo",349:"Feebas",350:"Milotic",351:"Castform",
    352:"Kecleon",353:"Shuppet",354:"Banette",355:"Duskull",356:"Dusclops",
    357:"Tropius",358:"Chimecho",359:"Absol",360:"Wynaut",361:"Snorunt",
    362:"Glalie",363:"Spheal",364:"Sealeo",365:"Walrein",366:"Clamperl",
    367:"Huntail",368:"Gorebyss",369:"Relicanth",370:"Luvdisc",371:"Bagon",
    372:"Shelgon",373:"Salamence",374:"Beldum",375:"Metang",376:"Metagross",
    377:"Regirock",378:"Regice",379:"Registeel",380:"Latias",381:"Latios",
    382:"Kyogre",383:"Groudon",384:"Rayquaza",385:"Jirachi",386:"Deoxys",
    387:"Turtwig",388:"Grotle",389:"Torterra",390:"Chimchar",391:"Monferno",
    392:"Infernape",393:"Piplup",394:"Prinplup",395:"Empoleon",396:"Starly",
    397:"Staravia",398:"Staraptor",399:"Bidoof",400:"Bibarel",401:"Kricketot",
    402:"Kricketune",403:"Shinx",404:"Luxio",405:"Luxray",406:"Budew",
    407:"Roserade",408:"Cranidos",409:"Rampardos",410:"Shieldon",411:"Bastiodon",
    412:"Burmy",413:"Wormadam",414:"Mothim",415:"Combee",416:"Vespiquen",
    417:"Pachirisu",418:"Buizel",419:"Floatzel",420:"Cherubi",421:"Cherrim",
    422:"Shellos",423:"Gastrodon",424:"Ambipom",425:"Drifloon",426:"Drifblim",
    427:"Buneary",428:"Lopunny",429:"Mismagius",430:"Honchkrow",431:"Glameow",
    432:"Purugly",433:"Chingling",434:"Stunky",435:"Skuntank",436:"Bronzor",
    437:"Bronzong",438:"Bonsly",439:"Mime Jr.",440:"Happiny",441:"Chatot",
    442:"Spiritomb",443:"Gible",444:"Gabite",445:"Garchomp",446:"Munchlax",
    447:"Riolu",448:"Lucario",449:"Hippopotas",450:"Hippowdon",451:"Skorupi",
    452:"Drapion",453:"Croagunk",454:"Toxicroak",455:"Carnivine",456:"Finneon",
    457:"Lumineon",458:"Mantyke",459:"Snover",460:"Abomasnow",461:"Weavile",
    462:"Magnezone",463:"Lickilicky",464:"Rhyperior",465:"Tangrowth",
    466:"Electivire",467:"Magmortar",468:"Togekiss",469:"Yanmega",470:"Leafeon",
    471:"Glaceon",472:"Gliscor",473:"Mamoswine",474:"Porygon-Z",475:"Gallade",
    476:"Probopass",477:"Dusknoir",478:"Froslass",479:"Rotom",480:"Uxie",
    481:"Mesprit",482:"Azelf",483:"Dialga",484:"Palkia",485:"Heatran",
    486:"Regigigas",487:"Giratina",488:"Cresselia",489:"Phione",490:"Manaphy",
    491:"Darkrai",492:"Shaymin",493:"Arceus",
}

TYPE_COLORS = {
    "Normal":"#A8A878","Fighting":"#C03028","Flying":"#A890F0","Poison":"#A040A0",
    "Ground":"#E0C068","Rock":"#B8A038","Bug":"#A8B820","Ghost":"#705898",
    "Steel":"#B8B8D0","Fire":"#F08030","Water":"#6890F0","Grass":"#78C850",
    "Electric":"#F8D030","Psychic":"#F85888","Ice":"#98D8D8","Dragon":"#7038F8",
    "Dark":"#705848","???":"#68A090",
}

SPECIES_TYPES = {
    1:["Grass","Poison"],2:["Grass","Poison"],3:["Grass","Poison"],
    4:["Fire",None],5:["Fire",None],6:["Fire","Flying"],
    7:["Water",None],8:["Water",None],9:["Water",None],
    10:["Bug",None],12:["Bug","Flying"],13:["Bug","Poison"],15:["Bug","Poison"],
    16:["Normal","Flying"],17:["Normal","Flying"],18:["Normal","Flying"],
    19:["Normal",None],20:["Normal",None],25:["Electric",None],26:["Electric",None],
    29:["Poison",None],31:["Poison","Ground"],32:["Poison",None],34:["Poison","Ground"],
    35:["Normal",None],37:["Fire",None],38:["Fire",None],39:["Normal",None],
    41:["Poison","Flying"],42:["Poison","Flying"],43:["Grass","Poison"],
    45:["Grass","Poison"],46:["Bug","Grass"],48:["Bug","Poison"],
    50:["Ground",None],52:["Normal",None],54:["Water",None],56:["Fighting",None],
    58:["Fire",None],59:["Fire",None],60:["Water",None],62:["Water","Fighting"],
    63:["Psychic",None],65:["Psychic",None],66:["Fighting",None],68:["Fighting",None],
    69:["Grass","Poison"],72:["Water","Poison"],74:["Rock","Ground"],76:["Rock","Ground"],
    77:["Fire",None],79:["Water","Psychic"],81:["Electric","Steel"],82:["Electric","Steel"],
    83:["Normal","Flying"],86:["Water",None],87:["Water","Ice"],
    88:["Poison",None],90:["Water",None],91:["Water","Ice"],
    92:["Ghost","Poison"],93:["Ghost","Poison"],94:["Ghost","Poison"],
    95:["Rock","Ground"],96:["Psychic",None],100:["Electric",None],
    102:["Grass","Psychic"],104:["Ground",None],106:["Fighting",None],107:["Fighting",None],
    109:["Poison",None],111:["Ground","Rock"],113:["Normal",None],114:["Grass",None],
    120:["Water",None],121:["Water","Psychic"],122:["Psychic",None],
    123:["Bug","Flying"],124:["Ice","Psychic"],125:["Electric",None],126:["Fire",None],
    129:["Water",None],130:["Water","Flying"],131:["Water","Ice"],132:["Normal",None],
    133:["Normal",None],134:["Water",None],135:["Electric",None],136:["Fire",None],
    142:["Rock","Flying"],143:["Normal",None],144:["Ice","Flying"],
    145:["Electric","Flying"],146:["Fire","Flying"],147:["Dragon",None],
    149:["Dragon","Flying"],150:["Psychic",None],151:["Psychic",None],
    152:["Grass",None],155:["Fire",None],158:["Water",None],
    196:["Psychic",None],197:["Dark",None],243:["Electric",None],
    244:["Fire",None],245:["Water",None],248:["Rock","Dark"],
    249:["Psychic","Flying"],250:["Fire","Flying"],251:["Psychic","Grass"],
    252:["Grass",None],255:["Fire",None],257:["Fire","Fighting"],
    258:["Water",None],260:["Water","Ground"],280:["Psychic",None],282:["Psychic",None],
    350:["Water",None],373:["Dragon","Flying"],376:["Steel","Psychic"],
    380:["Dragon","Psychic"],381:["Dragon","Psychic"],382:["Water",None],
    383:["Ground","Fire"],384:["Dragon","Flying"],386:["Psychic",None],
    387:["Grass",None],389:["Grass","Ground"],390:["Fire",None],
    392:["Fire","Fighting"],393:["Water",None],395:["Water","Steel"],
    396:["Normal","Flying"],398:["Normal","Flying"],403:["Electric",None],
    405:["Electric",None],408:["Rock",None],410:["Rock","Steel"],
    415:["Bug","Flying"],417:["Electric",None],418:["Water",None],
    422:["Water",None],423:["Water","Ground"],425:["Ghost","Flying"],
    427:["Normal",None],431:["Normal",None],434:["Poison","Dark"],
    436:["Steel","Psychic"],437:["Steel","Psychic"],442:["Ghost","Dark"],
    443:["Dragon",None],444:["Dragon","Ground"],445:["Dragon","Ground"],
    446:["Normal",None],447:["Fighting",None],448:["Fighting","Steel"],
    449:["Ground",None],451:["Bug","Poison"],452:["Bug","Dark"],
    453:["Poison","Fighting"],459:["Grass","Ice"],461:["Dark","Ice"],
    462:["Electric","Steel"],464:["Ground","Rock"],468:["Normal","Flying"],
    469:["Bug","Flying"],470:["Grass",None],471:["Ice",None],472:["Ground","Flying"],
    473:["Ice","Ground"],475:["Psychic","Fighting"],476:["Rock","Steel"],
    478:["Ice","Ghost"],479:["Electric","Ghost"],480:["Psychic",None],
    483:["Steel","Dragon"],484:["Water","Dragon"],487:["Ghost","Dragon"],
    491:["Dark",None],492:["Grass",None],493:["Normal",None],
}

# ============================================================
# DECODIFICACION DE STRINGS
# ============================================================
GBA_CHARSET = {
    0xBB:'A',0xBC:'B',0xBD:'C',0xBE:'D',0xBF:'E',0xC0:'F',0xC1:'G',0xC2:'H',
    0xC3:'I',0xC4:'J',0xC5:'K',0xC6:'L',0xC7:'M',0xC8:'N',0xC9:'O',0xCA:'P',
    0xCB:'Q',0xCC:'R',0xCD:'S',0xCE:'T',0xCF:'U',0xD0:'V',0xD1:'W',0xD2:'X',
    0xD3:'Y',0xD4:'Z',0xD5:'a',0xD6:'b',0xD7:'c',0xD8:'d',0xD9:'e',0xDA:'f',
    0xDB:'g',0xDC:'h',0xDD:'i',0xDE:'j',0xDF:'k',0xE0:'l',0xE1:'m',0xE2:'n',
    0xE3:'o',0xE4:'p',0xE5:'q',0xE6:'r',0xE7:'s',0xE8:'t',0xE9:'u',0xEA:'v',
    0xEB:'w',0xEC:'x',0xED:'y',0xEE:'z',
    0xA1:'0',0xA2:'1',0xA3:'2',0xA4:'3',0xA5:'4',0xA6:'5',0xA7:'6',0xA8:'7',
    0xA9:'8',0xAA:'9',0xFF:' ',
}

def decode_gba_str(data, offset, length=7):
    r = ""
    for i in range(length):
        if offset+i >= len(data): break
        b = data[offset+i]
        if b == 0xFF: break
        r += GBA_CHARSET.get(b, '?')
    return r.strip()

def decode_nds_str(data, offset, max_chars=16):
    r = ""
    for i in range(max_chars):
        pos = offset + i*2
        if pos+2 > len(data): break
        ch = struct.unpack_from("<H", data, pos)[0]
        if ch in (0xFFFF, 0x0000): break
        if 0x20 <= ch <= 0x7E: r += chr(ch)
        elif ch == 0x2642: r += "♂"
        elif ch == 0x2640: r += "♀"
    return r.strip()

# ============================================================
# PRNG / DECRYPT NDS PK4
# ============================================================
BLOCK_ORDERS = [
    "ABCD","ABDC","ACBD","ACDB","ADBC","ADCB","BACD","BADC","BCAD","BCDA",
    "BDAC","BDCA","CABD","CADB","CBAD","CBDA","CDAB","CDBA","DABC","DACB",
    "DBAC","DBCA","DCAB","DCBA",
]

def decrypt_pk4(raw):
    if len(raw) < 136: return None
    pid      = struct.unpack_from("<I", raw, 0)[0]
    checksum = struct.unpack_from("<H", raw, 6)[0]
    seed = checksum
    dec = bytearray(raw[:8])
    for i in range(0, 128, 2):
        seed = (seed * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
        w = struct.unpack_from("<H", raw, 8+i)[0]
        dec += struct.pack("<H", w ^ ((seed >> 16) & 0xFFFF))
    return bytes(dec)

def get_block(dec, pid, letter):
    idx   = BLOCK_ORDERS[pid % 24].index(letter)
    start = 8 + idx * 32
    return dec[start:start+32]

# ============================================================
# PARSE PK4 - intento directo
# ============================================================
def parse_pk4(raw):
    if len(raw) < 136: return None
    pid = struct.unpack_from("<I", raw, 0)[0]
    if pid == 0: return None

    dec = decrypt_pk4(raw)
    if not dec: return None

    ba = get_block(dec, pid, 'A')
    species_id = struct.unpack_from("<H", ba, 0)[0]
    if species_id == 0 or species_id > 493: return None

    exp = struct.unpack_from("<I", ba, 4)[0]

    # moves from block B
    bb = get_block(dec, pid, 'B')
    moves = [struct.unpack_from("<H", bb, i*2)[0] for i in range(4)]

    # nickname from block D (11 chars x 2 bytes)
    bd = get_block(dec, pid, 'D')
    nickname = ""
    for i in range(11):
        if i*2+2 > len(bd): break
        ch = struct.unpack_from("<H", bd, i*2)[0]
        if ch in (0xFFFF, 0x0000): break
        if 0x20 <= ch <= 0x7E: nickname += chr(ch)
        elif ch == 0x2642: nickname += "♂"
        elif ch == 0x2640: nickname += "♀"

    # OT name + OTID from block C
    bc = get_block(dec, pid, 'C')
    ot_name = ""
    for i in range(8):
        if i*2+2 > len(bc): break
        ch = struct.unpack_from("<H", bc, i*2)[0]
        if ch in (0xFFFF, 0x0000): break
        if 0x20 <= ch <= 0x7E: ot_name += chr(ch)

    otid   = struct.unpack_from("<I", bc, 0x10)[0] if len(bc) >= 0x14 else 0
    tid    = otid & 0xFFFF
    sid    = (otid >> 16) & 0xFFFF
    shiny  = (tid ^ sid ^ (pid>>16) ^ (pid&0xFFFF)) < 8
    level  = exp_to_level(exp)
    types  = SPECIES_TYPES.get(species_id, ["Normal", None])
    name   = POKEMON_NAMES.get(species_id, f"PKM#{species_id}")
    nick   = nickname.strip()
    if nick == name: nick = ""

    return build_pkmn(species_id, name, nick, level, exp, shiny, pid, tid, ot_name.strip(), types, [m for m in moves if m])

def build_pkmn(species_id, name, nick, level, exp, shiny, pid, tid, ot, types, moves):
    return {
        "species_id": species_id,
        "name":       name,
        "nickname":   nick,
        "level":      level,
        "exp":        exp,
        "is_shiny":   shiny,
        "pid":        pid,
        "trainer_id": tid,
        "ot_name":    ot,
        "type1":      types[0],
        "type2":      types[1],
        "type1_color": TYPE_COLORS.get(types[0], "#888"),
        "type2_color": TYPE_COLORS.get(types[1], "#888") if types[1] else None,
        "moves":      moves,
    }

def exp_to_level(exp):
    for lv in range(100, 0, -1):
        if lv**3 <= exp: return min(lv+1, 100)
    return 1

# ============================================================
# DETECCION DEL JUEGO
# ============================================================
def detect_game(data):
    size = len(data)
    markers = {
        b"CPUE":"platinum", b"CPUD":"platinum", b"CPUJ":"platinum",
        b"ADAE":"diamond_pearl", b"APAE":"diamond_pearl",
        b"ADAD":"diamond_pearl", b"APAD":"diamond_pearl",
        b"IPGE":"hgss", b"IPKE":"hgss", b"IPGD":"hgss", b"IPKD":"hgss",
    }
    for sig, game in markers.items():
        if sig in data[:1024]: return game
    if size == 131072:  return "firered"   # 128 KB -> GBA
    if size == 524288:  return "platinum"  # 512 KB -> NDS, asumir platino
    return None

def decode_trainer_name(data, game_key, offset):
    if game_key in ("firered","emerald"):
        return decode_gba_str(data, offset, 7)
    return decode_nds_str(data, offset, 8)

def decode_box_name(data, game_key, base, idx):
    if game_key in ("firered","emerald") or base is None:
        return f"CAJA {idx+1}"
    name = decode_nds_str(data, base + idx*18, 9)
    return name if name else f"CAJA {idx+1}"

# ============================================================
# LEER CAJAS - intento directo con parser PK4
# ============================================================
def read_boxes_direct(data, game_key):
    cfg = GAME_OFFSETS[game_key]
    boxes = []
    for bi in range(cfg["boxes"]):
        box_offset = cfg["storage"] + bi * BOX_SIZE
        name = decode_box_name(data, game_key, cfg["box_names"], bi)
        slots = []
        for si in range(SLOTS_PER_BOX):
            off = box_offset + si * POKEMON_SIZE
            if off + POKEMON_SIZE > len(data):
                slots.append(None); continue
            raw = bytes(data[off:off+POKEMON_SIZE])
            slots.append(parse_pk4(raw))
        boxes.append({"name": name, "index": bi,
                      "pokemon": slots,
                      "count": sum(1 for s in slots if s)})
    return boxes

# ============================================================
# FALLBACK: Claude API analiza hex del save para encontrar Pokemon
# ============================================================
import urllib.request

def ask_claude_for_pokemon(hex_sample, game_name, filename):
    """
    Envia un fragmento del save en hex a Claude API.
    Claude devuelve una lista de Pokemon que encuentra,
    inferidos de los datos binarios.
    """
    prompt = f"""Eres un experto en el formato binario de saves de Pokemon {game_name}.
Te voy a dar un fragmento hexadecimal del archivo de guardado '{filename}'.
Tu tarea es encontrar todos los Pokemon que haya en las cajas del PC.

Para cada Pokemon encontrado, devuelve un JSON con esta estructura exacta:
{{
  "pokemon": [
    {{
      "box": 0,
      "slot": 0,
      "species_id": 25,
      "name": "Pikachu",
      "nickname": "",
      "level": 50,
      "is_shiny": false,
      "type1": "Electric",
      "type2": null,
      "ot_name": "RED",
      "trainer_id": 12345
    }}
  ]
}}

Reglas:
- box y slot empiezan en 0
- species_id del 1 al 493
- Solo incluye slots NO vacios
- Si no puedes determinar un campo con certeza, usa valores por defecto razonables
- Devuelve SOLO el JSON, sin texto adicional, sin markdown

Aqui estan los primeros bytes de cada caja del PC en hex (offset : bytes):
{hex_sample}
"""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            text += block["text"]

    # Extraer JSON de la respuesta
    text = text.strip()
    text = re.sub(r"```json|```", "", text).strip()
    parsed = json.loads(text)
    return parsed.get("pokemon", [])


def build_boxes_from_claude(pokemon_list, game_key):
    cfg = GAME_OFFSETS[game_key]
    num_boxes = cfg["boxes"]

    # Inicializar cajas vacias
    boxes = [{"name": f"CAJA {i+1}", "index": i,
               "pokemon": [None]*SLOTS_PER_BOX, "count": 0}
             for i in range(num_boxes)]

    for pk in pokemon_list:
        bi = pk.get("box", 0)
        si = pk.get("slot", 0)
        if bi >= num_boxes or si >= SLOTS_PER_BOX: continue

        sid   = pk.get("species_id", 0)
        name  = pk.get("name") or POKEMON_NAMES.get(sid, f"PKM#{sid}")
        types = SPECIES_TYPES.get(sid, ["Normal", None])
        t1    = pk.get("type1") or types[0]
        t2    = pk.get("type2") or types[1]

        boxes[bi]["pokemon"][si] = {
            "species_id": sid,
            "name":       name,
            "nickname":   pk.get("nickname",""),
            "level":      pk.get("level", 1),
            "exp":        0,
            "is_shiny":   pk.get("is_shiny", False),
            "pid":        0,
            "trainer_id": pk.get("trainer_id", 0),
            "ot_name":    pk.get("ot_name",""),
            "type1":      t1,
            "type2":      t2,
            "type1_color": TYPE_COLORS.get(t1,"#888"),
            "type2_color": TYPE_COLORS.get(t2,"#888") if t2 else None,
            "moves":      [],
        }
        boxes[bi]["count"] += 1

    return boxes


def hex_sample_for_claude(data, game_key):
    """
    Extrae un fragmento representativo del save en hex
    para enviarlo a Claude (limitado para no superar tokens).
    Toma los primeros 512 bytes de cada caja (6 cajas max).
    """
    cfg = GAME_OFFSETS[game_key]
    lines = []
    for bi in range(min(cfg["boxes"], 6)):
        off = cfg["storage"] + bi * BOX_SIZE
        chunk = data[off:off+512]
        hex_str = chunk.hex()
        lines.append(f"CAJA {bi} offset=0x{off:X}: {hex_str}")
    return "\n".join(lines)


# ============================================================
# FLASK ROUTES
# ============================================================
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/upload", methods=["POST"])
def upload_save():
    if "file" not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400

    file = request.files["file"]
    data = file.read()

    if len(data) < 50000:
        return jsonify({"error": f"Archivo muy pequeño ({len(data)} bytes)"}), 400

    game_key = detect_game(data)
    if not game_key:
        return jsonify({"error": "Formato no reconocido. Soporta: Platino, Diamante, Perla, HGSS, FireRed, Esmeralda"}), 400

    game_names = {
        "platinum":"Pokémon Platino","diamond_pearl":"Pokémon Diamante/Perla",
        "hgss":"Pokémon HeartGold/SoulSilver","firered":"Pokémon FireRed/LeafGreen",
        "emerald":"Pokémon Esmeralda",
    }

    cfg = GAME_OFFSETS[game_key]

    # Info entrenador
    trainer_name = decode_trainer_name(data, game_key, cfg["trainer_name"])
    trainer_id   = struct.unpack_from("<H", data, cfg["trainer_id"])[0] if cfg["trainer_id"]+2 < len(data) else 0

    # --- INTENTO 1: parser directo ---
    try:
        boxes = read_boxes_direct(data, game_key)
        total = sum(b["count"] for b in boxes)
    except Exception:
        boxes = []
        total = 0

    # --- INTENTO 2: si no encontramos nada, usar Claude API ---
    used_api = False
    if total == 0:
        try:
            hex_sample = hex_sample_for_claude(data, game_key)
            pkmn_list  = ask_claude_for_pokemon(hex_sample, game_names[game_key], file.filename)
            if pkmn_list:
                boxes     = build_boxes_from_claude(pkmn_list, game_key)
                total     = sum(b["count"] for b in boxes)
                used_api  = True
        except Exception as e:
            # Si la API falla, devolvemos cajas vacias con mensaje
            return jsonify({
                "filename": file.filename,
                "game":     game_names[game_key],
                "trainer":  {"name": trainer_name, "trainer_id": trainer_id},
                "total_pokemon": 0,
                "boxes":    boxes,
                "warning":  f"No se encontraron Pokémon con el parser directo y la API falló: {str(e)}"
            })

    return jsonify({
        "filename":      file.filename,
        "game":          game_names[game_key],
        "trainer":       {"name": trainer_name, "trainer_id": trainer_id},
        "total_pokemon": total,
        "boxes":         boxes,
        "used_api":      used_api,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("Pokemon PC Box Viewer")
    print("Parser directo + fallback Claude API")
    print("http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)