# Maps *every* commonly-seen spelling / abbreviation → canonical USPS suffix
street_type_map: dict[str, str] = {
    # ――― A ―――
    "ALY": "ALLEY", "ALLEE": "ALLEY", "ALLY": "ALLEY", "ALLEY": "ALLEY",
    "ANX": "ANNEX", "ANEX": "ANNEX", "ANNEX": "ANNEX",
    "ARC": "ARCADE", "ARCADE": "ARCADE",
    "AV": "AVENUE", "AVE": "AVENUE", "AVEN": "AVENUE", "AVENU": "AVENUE",
    "AVN": "AVENUE", "AVNUE": "AVENUE", "AVENUE": "AVENUE",
    # ――― B ―――
    "BYU": "BAYOU", "BAYOO": "BAYOU", "BAYOU": "BAYOU",
    "BCH": "BEACH", "BEACH": "BEACH",
    "BND": "BEND", "BEND": "BEND",
    "BLF": "BLUFF", "BLUF": "BLUFF", "BLUFF": "BLUFF",
    "BLFS": "BLUFFS", "BLUFFS": "BLUFFS",
    "BTM": "BOTTOM", "BOTTM": "BOTTOM", "BOT": "BOTTOM", "BOTTOM": "BOTTOM",
    "BLVD": "BOULEVARD", "BOUL": "BOULEVARD", "BOULV": "BOULEVARD",
    "BOULEVARD": "BOULEVARD",
    "BR": "BRANCH", "BRNCH": "BRANCH", "BRANCH": "BRANCH",
    "BRG": "BRIDGE", "BRDGE": "BRIDGE", "BRIDGE": "BRIDGE",
    "BRK": "BROOK", "BROOK": "BROOK",
    "BRKS": "BROOKS", "BROOKS": "BROOKS",
    "BG": "BURG", "BURG": "BURG",
    "BGS": "BURGS", "BURGS": "BURGS",
    "BYP": "BYPASS", "BYPA": "BYPASS", "BYPAS": "BYPASS",
    "BYPS": "BYPASS", "BYPASS": "BYPASS",
    # ――― C ―――
    "CP": "CAMP", "CMP": "CAMP", "CAMP": "CAMP",
    "CYN": "CANYON", "CNYN": "CANYON", "CANYN": "CANYON", "CANYON": "CANYON",
    "CPE": "CAPE", "CAPE": "CAPE",
    "CSWY": "CAUSEWAY", "CAUSEWAY": "CAUSEWAY", "CAUSWA": "CAUSEWAY",
    "CEN": "CENTER", "CENT": "CENTER", "CENTER": "CENTER", "CENTR": "CENTER",
    "CENTRE": "CENTER", "CNTER": "CENTER", "CNTR": "CENTER",
    "CTRS": "CENTERS", "CENTERS": "CENTERS",
    "CIR": "CIRCLE", "CIRC": "CIRCLE", "CIRCL": "CIRCLE",
    "CRCL": "CIRCLE", "CRCLE": "CIRCLE", "CIRCLE": "CIRCLE",
    "CIRS": "CIRCLES", "CIRCLES": "CIRCLES",
    "CLF": "CLIFF", "CLIFF": "CLIFF",
    "CLFS": "CLIFFS", "CLIFFS": "CLIFFS",
    "CLB": "CLUB", "CLUB": "CLUB",
    "CMN": "COMMON", "COMMON": "COMMON",
    "CMNS": "COMMONS", "COMMONS": "COMMONS",
    "COR": "CORNER", "CORNER": "CORNER",
    "CORS": "CORNERS", "CORNERS": "CORNERS",
    "CRSE": "COURSE", "COURSE": "COURSE",
    "CT": "COURT", "COURT": "COURT",
    "CTS": "COURTS", "COURTS": "COURTS",
    "CV": "COVE", "COVE": "COVE",
    "CVS": "COVES", "COVES": "COVES",
    "CRK": "CREEK", "CREEK": "CREEK",
    "CRES": "CRESCENT", "CRSENT": "CRESCENT", "CRSNT": "CRESCENT",
    "CRESCENT": "CRESCENT",
    "CRST": "CREST", "CREST": "CREST",
    "XING": "CROSSING", "CRSSNG": "CROSSING", "CROSSING": "CROSSING",
    "XRD": "CROSSROAD", "CROSSROAD": "CROSSROAD",
    "XRDS": "CROSSROADS", "CROSSROADS": "CROSSROADS",
    "CURV": "CURVE", "CURVE": "CURVE",
    # ――― D ―――
    "DL": "DALE", "DALE": "DALE",
    "DM": "DAM", "DAM": "DAM",
    "DV": "DIVIDE", "DIV": "DIVIDE", "DVD": "DIVIDE", "DIVIDE": "DIVIDE",
    "DR": "DRIVE", "DRIV": "DRIVE", "DRV": "DRIVE", "DRIVE": "DRIVE",
    "DRS": "DRIVES", "DRIVES": "DRIVES",
    # ――― E ―――
    "EST": "ESTATE", "ESTATE": "ESTATE",
    "ESTS": "ESTATES", "ESTATES": "ESTATES",
    "EXP": "EXPRESSWAY", "EXPY": "EXPRESSWAY", "EXPR": "EXPRESSWAY",
    "EXPRESS": "EXPRESSWAY", "EXPW": "EXPRESSWAY", "EXPRESSWAY": "EXPRESSWAY",
    "EXT": "EXTENSION", "EXTN": "EXTENSION", "EXTNSN": "EXTENSION",
    "EXTENSION": "EXTENSION",
    "EXTS": "EXTENSIONS", "EXTENSIONS": "EXTENSIONS",
    # ――― F ―――
    "FALL": "FALL", "FLS": "FALLS", "FALLS": "FALLS",
    "FRY": "FERRY", "FRRY": "FERRY", "FERRY": "FERRY",
    "FLD": "FIELD", "FIELD": "FIELD",
    "FLDS": "FIELDS", "FIELDS": "FIELDS",
    "FLT": "FLAT", "FLAT": "FLAT",
    "FLTS": "FLATS", "FLATS": "FLATS",
    "FRD": "FORD", "FORD": "FORD",
    "FRDS": "FORDS", "FORDS": "FORDS",
    "FRST": "FOREST", "FOREST": "FOREST",
    "FORG": "FORGE", "FRG": "FORGE", "FORGE": "FORGE",
    "FRGS": "FORGES", "FORGES": "FORGES",
    "FRK": "FORK", "FORK": "FORK",
    "FRKS": "FORKS", "FORKS": "FORKS",
    "FT": "FORT", "FRT": "FORT", "FORT": "FORT",
    "FWY": "FREEWAY", "FREEWAY": "FREEWAY", "FREEWY": "FREEWAY",
    "FRWAY": "FREEWAY", "FRWY": "FREEWAY",
    # ――― G ―――
    "GDN": "GARDEN", "GARDN": "GARDEN", "GRDEN": "GARDEN", "GRDN": "GARDEN",
    "GARDEN": "GARDEN",
    "GDNS": "GARDENS", "GRDNS": "GARDENS", "GARDENS": "GARDENS",
    "GTWY": "GATEWAY", "GATEWY": "GATEWAY", "GATWAY": "GATEWAY",
    "GTWAY": "GATEWAY", "GATEWAY": "GATEWAY",
    "GLN": "GLEN", "GLEN": "GLEN",
    "GLNS": "GLENS", "GLENS": "GLENS",
    "GRN": "GREEN", "GREEN": "GREEN",
    "GRNS": "GREENS", "GREENS": "GREENS",
    "GRV": "GROVE", "GROV": "GROVE", "GROVE": "GROVE",
    "GRVS": "GROVES", "GROVES": "GROVES",
    # ――― H ―――
    "HBR": "HARBOR", "HARB": "HARBOR", "HARBR": "HARBOR",
    "HRBOR": "HARBOR", "HARBOR": "HARBOR",
    "HBRS": "HARBORS", "HARBORS": "HARBORS",
    "HVN": "HAVEN", "HAVEN": "HAVEN",
    "HTS": "HEIGHTS", "HT": "HEIGHTS", "HEIGHTS": "HEIGHTS",
    "HWY": "HIGHWAY", "HIGHWAY": "HIGHWAY", "HIGHWY": "HIGHWAY",
    "HIWAY": "HIGHWAY", "HIWY": "HIGHWAY", "HWAY": "HIGHWAY",
    "HL": "HILL", "HILL": "HILL",
    "HLS": "HILLS", "HILLS": "HILLS",
    "HOLW": "HOLLOW", "HLLW": "HOLLOW", "HOLLOW": "HOLLOW",
    "HOLWS": "HOLLOW", "HOLLOWS": "HOLLOW",
    # ――― I ―――
    "INLT": "INLET", "INLET": "INLET",
    "IS": "ISLAND", "ISLND": "ISLAND", "ISLAND": "ISLAND",
    "ISS": "ISLANDS", "ISLNDS": "ISLANDS", "ISLANDS": "ISLANDS",
    "ISLE": "ISLE", "ISLES": "ISLES",
    # ――― J ―――
    "JCT": "JUNCTION", "JCTION": "JUNCTION", "JCTN": "JUNCTION",
    "JUNCTN": "JUNCTION", "JUNCTON": "JUNCTION", "JUNCTION": "JUNCTION",
    "JCTNS": "JUNCTIONS", "JCTS": "JUNCTIONS", "JUNCTIONS": "JUNCTIONS",
    # ――― K ―――
    "KY": "KEY", "KEY": "KEY",
    "KYS": "KEYS", "KEYS": "KEYS",
    "KNL": "KNOLL", "KNOL": "KNOLL", "KNOLL": "KNOLL",
    "KNLS": "KNOLLS", "KNOLLS": "KNOLLS",
    # ――― L ―――
    "LK": "LAKE", "LAKE": "LAKE",
    "LKS": "LAKES", "LAKES": "LAKES",
    "LAND": "LAND",
    "LNDG": "LANDING", "LNDNG": "LANDING", "LANDING": "LANDING",
    "LN": "LANE", "LANE": "LANE",
    "LGT": "LIGHT", "LIGHT": "LIGHT",
    "LGTS": "LIGHTS", "LIGHTS": "LIGHTS",
    "LF": "LOAF", "LOAF": "LOAF",
    "LCK": "LOCK", "LOCK": "LOCK",
    "LCKS": "LOCKS", "LOCKS": "LOCKS",
    "LDG": "LODGE", "LDGE": "LODGE", "LODG": "LODGE", "LODGE": "LODGE",
    "LOOP": "LOOP", "LOOPS": "LOOP",
    # ――― M ―――
    "MALL": "MALL",
    "MNR": "MANOR", "MANOR": "MANOR",
    "MNRS": "MANORS", "MANORS": "MANORS",
    "MDW": "MEADOW", "MEADOW": "MEADOW",
    "MDWS": "MEADOWS", "MEDOWS": "MEADOWS", "MEADOWS": "MEADOWS",
    "MEWS": "MEWS",
    "ML": "MILL", "MILL": "MILL",
    "MLS": "MILLS", "MILLS": "MILLS",
    "MSN": "MISSION", "MISSN": "MISSION", "MSSN": "MISSION",
    "MISSION": "MISSION",
    "MTWY": "MOTORWAY", "MOTORWAY": "MOTORWAY",
    "MT": "MOUNT", "MNT": "MOUNT", "MOUNT": "MOUNT",
    "MTN": "MOUNTAIN", "MNTAIN": "MOUNTAIN", "MNTN": "MOUNTAIN",
    "MOUNTIN": "MOUNTAIN", "MTIN": "MOUNTAIN", "MOUNTAIN": "MOUNTAIN",
    "MTNS": "MOUNTAINS", "MNTNS": "MOUNTAINS", "MOUNTAINS": "MOUNTAINS",
    # ――― N ―――
    "NCK": "NECK", "NECK": "NECK",
    # ――― O ―――
    "ORCH": "ORCHARD", "ORCHRD": "ORCHARD", "ORCHARD": "ORCHARD",
    "OVAL": "OVAL", "OVL": "OVAL",
    "OPAS": "OVERPASS", "OVERPASS": "OVERPASS",
    # ――― P ―――
    "PARK": "PARK", "PRK": "PARK",
    "PARKS": "PARKS",
    "PKWY": "PARKWAY", "PARKWAY": "PARKWAY", "PARKWY": "PARKWAY",
    "PKWAY": "PARKWAY", "PKY": "PARKWAY",
    "PKWYS": "PARKWAYS", "PARKWAYS": "PARKWAYS",
    "PASS": "PASS",
    "PSGE": "PASSAGE", "PASSAGE": "PASSAGE",
    "PATH": "PATH", "PATHS": "PATHS",
    "PIKE": "PIKE", "PIKES": "PIKES",
    "PNE": "PINE", "PINE": "PINE",
    "PNES": "PINES", "PINES": "PINES",
    "PL": "PLACE", "PLACE": "PLACE",
    "PLN": "PLAIN", "PLAIN": "PLAIN",
    "PLNS": "PLAINS", "PLAINS": "PLAINS",
    "PLZ": "PLAZA", "PLAZA": "PLAZA", "PLZA": "PLAZA",
    "PT": "POINT", "POINT": "POINT",
    "PTS": "POINTS", "POINTS": "POINTS",
    "PRT": "PORT", "PORT": "PORT",
    "PRTS": "PORTS", "PORTS": "PORTS",
    "PR": "PRAIRIE", "PRAIRIE": "PRAIRIE", "PRR": "PRAIRIE",
    # ――― R ―――
    "RAD": "RADIAL", "RADL": "RADIAL", "RADIEL": "RADIAL", "RADIAL": "RADIAL",
    "RAMP": "RAMP",
    "RNCH": "RANCH", "RANCH": "RANCH",
    "RNCHS": "RANCHES", "RANCHES": "RANCHES",
    "RPD": "RAPID", "RAPID": "RAPID",
    "RPDS": "RAPIDS", "RAPIDS": "RAPIDS",
    "RST": "REST", "REST": "REST",
    "RDG": "RIDGE", "RDGE": "RIDGE", "RIDGE": "RIDGE",
    "RDGS": "RIDGES", "RIDGES": "RIDGES",
    "RIV": "RIVER", "RIVR": "RIVER", "RVR": "RIVER", "RIVER": "RIVER",
    "RD": "ROAD", "ROAD": "ROAD",
    "RDS": "ROADS", "ROADS": "ROADS",
    "RTE": "ROUTE", "ROUTE": "ROUTE",
    "ROW": "ROW",
    "RUE": "RUE",
    "RUN": "RUN",
    # ――― S ―――
    "SHL": "SHOAL", "SHOAL": "SHOAL",
    "SHLS": "SHOALS", "SHOALS": "SHOALS",
    "SHR": "SHORE", "SHOAR": "SHORE", "SHORE": "SHORE",
    "SHRS": "SHORES", "SHOARS": "SHORES", "SHORES": "SHORES",
    "SKWY": "SKYWAY", "SKYWAY": "SKYWAY",
    "SPG": "SPRING", "SPNG": "SPRING", "SPRNG": "SPRING", "SPRING": "SPRING",
    "SPGS": "SPRINGS", "SPNGS": "SPRINGS",
    "SPRNGS": "SPRINGS", "SPRINGS": "SPRINGS",
    "SPUR": "SPUR", "SPURS": "SPURS",
    "SQ": "SQUARE", "SQR": "SQUARE", "SQRE": "SQUARE",
    "SQU": "SQUARE", "SQUARE": "SQUARE",
    "SQRS": "SQUARES", "SQS": "SQUARES", "SQUARES": "SQUARES",
    "STA": "STATION", "STATN": "STATION", "STN": "STATION",
    "STATION": "STATION",
    "STRA": "STRAVENUE", "STRAV": "STRAVENUE", "STRAVEN": "STRAVENUE",
    "STRAVN": "STRAVENUE", "STRVN": "STRAVENUE",
    "STRVNUE": "STRAVENUE", "STRAVENUE": "STRAVENUE",
    "STRM": "STREAM", "STREME": "STREAM", "STREAM": "STREAM",
    "ST": "STREET", "STR": "STREET", "STRT": "STREET", "STREET": "STREET",
    "STS": "STREETS", "STREETS": "STREETS",
    "SMT": "SUMMIT", "SUMIT": "SUMMIT", "SUMITT": "SUMMIT", "SUMMIT": "SUMMIT",
    # ――― T ―――
    "TER": "TERRACE", "TERR": "TERRACE", "TERRACE": "TERRACE",
    "TRWY": "THROUGHWAY", "THROUGHWAY": "THROUGHWAY",
    "TRCE": "TRACE", "TRACE": "TRACE",
    "TRAK": "TRACK", "TRACK": "TRACK",
    "TRKS": "TRACKS", "TRK": "TRACKS", "TRACKS": "TRACKS",
    "TRFY": "TRAFFICWAY", "TRAFFICWAY": "TRAFFICWAY",
    "TRL": "TRAIL", "TRAIL": "TRAIL",
    "TRLS": "TRAILS", "TRAILS": "TRAILS",
    "TRLR": "TRAILER", "TRLRS": "TRAILER", "TRAILER": "TRAILER",
    "TUNL": "TUNNEL", "TUNLS": "TUNNEL", "TUNEL": "TUNNEL",
    "TUNNL": "TUNNEL", "TUNNEL": "TUNNEL",
    "TPKE": "TURNPIKE", "TRNPK": "TURNPIKE", "TURNPK": "TURNPIKE",
    "TURNPIKE": "TURNPIKE",
    "UPAS": "UNDERPASS", "UNDERPASS": "UNDERPASS",
    # ――― U ―――
    "UN": "UNION", "UNION": "UNION",
    "UNS": "UNIONS", "UNIONS": "UNIONS",
    # ――― V ―――
    "VLY": "VALLEY", "VALLY": "VALLEY", "VLLY": "VALLEY", "VALLEY": "VALLEY",
    "VLYS": "VALLEYS", "VALLEYS": "VALLEYS",
    "VIA": "VIADUCT", "VDCT": "VIADUCT", "VIADCT": "VIADUCT",
    "VIADUCT": "VIADUCT",
    "VW": "VIEW", "VIEW": "VIEW",
    "VWS": "VIEWS", "VIEWS": "VIEWS",
    "VLG": "VILLAGE", "VILL": "VILLAGE", "VILLAG": "VILLAGE",
    "VILLG": "VILLAGE", "VILLIAGE": "VILLAGE", "VILLAGE": "VILLAGE",
    "VLGS": "VILLAGES", "VILLAGES": "VILLAGES",
    "VL": "VILLE", "VILLE": "VILLE",
    "VIS": "VISTA", "VST": "VISTA", "VSTA": "VISTA", "VIST": "VISTA",
    "VISTA": "VISTA",
    # ――― W ―――
    "WALK": "WALK", "WALKS": "WALK",
    "WALL": "WALL",
    "WY": "WAY", "WAY": "WAY",
    "WAYS": "WAYS",
    "WL": "WELL", "WELL": "WELL",
    "WLS": "WELLS", "WELLS": "WELLS",
}

# Canonical street-suffix  ➜  USPS standard suffix abbreviation
canonical_to_abbrev: dict[str, str] = {
    # ――― A ―――
    "ALLEY":        "ALY",
    "ANNEX":        "ANX",
    "ARCADE":       "ARC",
    "AVENUE":       "AVE",

    # ――― B ―――
    "BAYOU":        "BYU",
    "BEACH":        "BCH",
    "BEND":         "BND",
    "BLUFF":        "BLF",
    "BLUFFS":       "BLFS",
    "BOTTOM":       "BTM",
    "BOULEVARD":    "BLVD",
    "BRANCH":       "BR",
    "BRIDGE":       "BRG",
    "BROOK":        "BRK",
    "BROOKS":       "BRKS",
    "BURG":         "BG",
    "BURGS":        "BGS",
    "BYPASS":       "BYP",

    # ――― C ―――
    "CAMP":         "CP",
    "CANYON":       "CYN",
    "CAPE":         "CPE",
    "CAUSEWAY":     "CSWY",
    "CENTER":       "CTR",
    "CENTERS":      "CTRS",
    "CIRCLE":       "CIR",
    "CIRCLES":      "CIRS",
    "CLIFF":        "CLF",
    "CLIFFS":       "CLFS",
    "CLUB":         "CLB",
    "COMMON":       "CMN",
    "COMMONS":      "CMNS",
    "CORNER":       "COR",
    "CORNERS":      "CORS",
    "COURSE":       "CRSE",
    "COURT":        "CT",
    "COURTS":       "CTS",
    "COVE":         "CV",
    "COVES":        "CVS",
    "CREEK":        "CRK",
    "CRESCENT":     "CRES",
    "CREST":        "CRST",
    "CROSSING":     "XING",
    "CROSSROAD":    "XRD",
    "CROSSROADS":   "XRDS",
    "CURVE":        "CURV",

    # ――― D ―――
    "DALE":         "DL",
    "DAM":          "DM",
    "DIVIDE":       "DV",
    "DRIVE":        "DR",
    "DRIVES":       "DRS",

    # ――― E ―――
    "ESTATE":       "EST",
    "ESTATES":      "ESTS",
    "EXPRESSWAY":   "EXPY",
    "EXTENSION":    "EXT",
    "EXTENSIONS":   "EXTS",

    # ――― F ―――
    "FALL":         "FALL",
    "FALLS":        "FLS",
    "FERRY":        "FRY",
    "FIELD":        "FLD",
    "FIELDS":       "FLDS",
    "FLAT":         "FLT",
    "FLATS":        "FLTS",
    "FORD":         "FRD",
    "FORDS":        "FRDS",
    "FOREST":       "FRST",
    "FORGE":        "FRG",
    "FORGES":       "FRGS",
    "FORK":         "FRK",
    "FORKS":        "FRKS",
    "FORT":         "FT",
    "FREEWAY":      "FWY",

    # ――― G ―――
    "GARDEN":       "GDN",
    "GARDENS":      "GDNS",
    "GATEWAY":      "GTWY",
    "GLEN":         "GLN",
    "GLENS":        "GLNS",
    "GREEN":        "GRN",
    "GREENS":       "GRNS",
    "GROVE":        "GRV",
    "GROVES":       "GRVS",

    # ――― H ―――
    "HARBOR":       "HBR",
    "HARBORS":      "HBRS",
    "HAVEN":        "HVN",
    "HEIGHTS":      "HTS",
    "HIGHWAY":      "HWY",
    "HILL":         "HL",
    "HILLS":        "HLS",
    "HOLLOW":       "HOLW",

    # ――― I ―――
    "INLET":        "INLT",
    "ISLAND":       "IS",
    "ISLANDS":      "ISS",
    "ISLE":         "ISLE",

    # ――― J ―――
    "JUNCTION":     "JCT",
    "JUNCTIONS":    "JCTS",

    # ――― K ―――
    "KEY":          "KY",
    "KEYS":         "KYS",
    "KNOLL":        "KNL",
    "KNOLLS":       "KNLS",

    # ――― L ―――
    "LAKE":         "LK",
    "LAKES":        "LKS",
    "LAND":         "LAND",
    "LANDING":      "LNDG",
    "LANE":         "LN",
    "LIGHT":        "LGT",
    "LIGHTS":       "LGTS",
    "LOAF":         "LF",
    "LOCK":         "LCK",
    "LOCKS":        "LCKS",
    "LODGE":        "LDG",
    "LOOP":         "LOOP",

    # ――― M ―――
    "MALL":         "MALL",
    "MANOR":        "MNR",
    "MANORS":       "MNRS",
    "MEADOW":       "MDW",
    "MEADOWS":      "MDWS",
    "MEWS":         "MEWS",
    "MILL":         "ML",
    "MILLS":        "MLS",
    "MISSION":      "MSN",
    "MOTORWAY":     "MTWY",
    "MOUNT":        "MT",
    "MOUNTAIN":     "MTN",
    "MOUNTAINS":    "MTNS",

    # ――― N ―――
    "NECK":         "NCK",

    # ――― O ―――
    "ORCHARD":      "ORCH",
    "OVAL":         "OVAL",
    "OVERPASS":     "OPAS",

    # ――― P ―――
    "PARK":         "PARK",
    "PARKS":        "PARKS",
    "PARKWAY":      "PKWY",
    "PARKWAYS":     "PKWY",
    "PASS":         "PASS",
    "PASSAGE":      "PSGE",
    "PATH":         "PATH",
    "PIKE":         "PIKE",
    "PINE":         "PNE",
    "PINES":        "PNES",
    "PLACE":        "PL",
    "PLAIN":        "PLN",
    "PLAINS":       "PLNS",
    "PLAZA":        "PLZ",
    "POINT":        "PT",
    "POINTS":       "PTS",
    "PORT":         "PRT",
    "PORTS":        "PRTS",
    "PRAIRIE":      "PR",

    # ――― R ―――
    "RADIAL":       "RADL",
    "RAMP":         "RAMP",
    "RANCH":        "RNCH",
    "RANCHES":      "RNCHS",
    "RAPID":        "RPD",
    "RAPIDS":       "RPDS",
    "REST":         "RST",
    "RIDGE":        "RDG",
    "RIDGES":       "RDGS",
    "RIVER":        "RIV",
    "ROAD":         "RD",
    "ROADS":        "RDS",
    "ROUTE":        "RTE",
    "ROW":          "ROW",
    "RUE":          "RUE",
    "RUN":          "RUN",

    # ――― S ―――
    "SHOAL":        "SHL",
    "SHOALS":       "SHLS",
    "SHORE":        "SHR",
    "SHORES":       "SHRS",
    "SKYWAY":       "SKWY",
    "SPRING":       "SPG",
    "SPRINGS":      "SPGS",
    "SPUR":         "SPUR",
    "SQUARE":       "SQ",
    "SQUARES":      "SQRS",
    "STATION":      "STA",
    "STRAVENUE":    "STRA",
    "STREAM":       "STRM",
    "STREET":       "ST",
    "STREETS":      "STS",
    "SUMMIT":       "SMT",

    # ――― T ―――
    "TERRACE":      "TER",
    "THROUGHWAY":   "TRWY",
    "TRACE":        "TRCE",
    "TRACK":        "TRAK",
    "TRACKS":       "TRKS",
    "TRAFFICWAY":   "TRFY",
    "TRAIL":        "TRL",
    "TRAILS":       "TRLS",
    "TRAILER":      "TRLR",
    "TUNNEL":       "TUNL",
    "TURNPIKE":     "TPKE",

    # ――― U ―――
    "UNDERPASS":    "UPAS",
    "UNION":        "UN",
    "UNIONS":       "UNS",

    # ――― V ―――
    "VALLEY":       "VLY",
    "VALLEYS":      "VLYS",
    "VIADUCT":      "VIA",
    "VIEW":         "VW",
    "VIEWS":        "VWS",
    "VILLAGE":      "VLG",
    "VILLAGES":     "VLGS",
    "VILLE":        "VL",
    "VISTA":        "VIS",

    # ――― W ―――
    "WALK":         "WALK",
    "WALL":         "WALL",
    "WAY":          "WAY",
    "WAYS":         "WAYS",
    "WELL":         "WL",
    "WELLS":        "WLS",
}

secondary_unit_type_map: dict[str, str] = {
    # — Apartment —
    "APT": "APARTMENT", "APT.": "APARTMENT", "APARTMENT": "APARTMENT",
    "APART": "APARTMENT", "APTMT": "APARTMENT",

    # — Basement —
    "BSMT": "BASEMENT", "BSMT.": "BASEMENT", "BASEMENT": "BASEMENT",
    "BSMENT": "BASEMENT", "BASMT": "BASEMENT",

    # — Building —
    "BLDG": "BUILDING", "BLDG.": "BUILDING", "BUILDING": "BUILDING",
    "BLDNG": "BUILDING",

    # — Department —
    "DEPT": "DEPARTMENT", "DEPT.": "DEPARTMENT", "DEPARTMENT": "DEPARTMENT",

    # — Floor —
    "FL": "FLOOR", "FL.": "FLOOR", "FLR": "FLOOR", "FLOOR": "FLOOR",

    # — Front —
    "FRNT": "FRONT", "FRNT.": "FRONT", "FRONT": "FRONT",

    # — Hangar —
    "HNGR": "HANGAR", "HNGR.": "HANGAR", "HANGER": "HANGAR", "HANGAR": "HANGAR",

    # — Key —
    "KEY": "KEY", "KEY.": "KEY",

    # — Lobby —
    "LBBY": "LOBBY", "LBBY.": "LOBBY", "LOBBY": "LOBBY",

    # — Lot —
    "LOT": "LOT", "LOT.": "LOT",

    # — Lower —
    "LOWR": "LOWER", "LOWR.": "LOWER", "LOWER": "LOWER",

    # — Office —
    "OFC": "OFFICE", "OFC.": "OFFICE", "OFFICE": "OFFICE", "OFFC": "OFFICE",

    # — Penthouse —
    "PH": "PENTHOUSE", "PH.": "PENTHOUSE", "PENTHOUSE": "PENTHOUSE",

    # — Pier —
    "PIER": "PIER", "PIER.": "PIER",

    # — Rear —
    "REAR": "REAR", "REAR.": "REAR",

    # — Room —
    "RM": "ROOM", "RM.": "ROOM", "ROOM": "ROOM",

    # — Side —
    "SIDE": "SIDE", "SIDE.": "SIDE",

    # — Slip —
    "SLIP": "SLIP", "SLIP.": "SLIP",

    # — Space —
    "SPC": "SPACE", "SPC.": "SPACE", "SPACE": "SPACE",

    # — Stop —
    "STOP": "STOP", "STOP.": "STOP",

    # — Suite —
    "STE": "SUITE", "STE.": "SUITE", "SUITE": "SUITE",

    # — Trailer —
    "TRLR": "TRAILER", "TRLR.": "TRAILER", "TRAILER": "TRAILER",

    # — Unit —
    "UNIT": "UNIT", "UNIT.": "UNIT",

    # — Upper —
    "UPPR": "UPPER", "UPPR.": "UPPER", "UPPER": "UPPER", "UPR": "UPPER",
}

secondary_unit_abbrev_map: dict[str, str] = {
    "APARTMENT":  "APT",
    "BASEMENT":   "BSMT",
    "BUILDING":   "BLDG",
    "DEPARTMENT": "DEPT",
    "FLOOR":      "FL",
    "FRONT":      "FRNT",
    "HANGAR":     "HNGR",
    "KEY":        "KEY",
    "LOBBY":      "LBBY",
    "LOT":        "LOT",
    "LOWER":      "LOWR",
    "OFFICE":     "OFC",
    "PENTHOUSE":  "PH",
    "PIER":       "PIER",
    "REAR":       "REAR",
    "ROOM":       "RM",
    "SIDE":       "SIDE",
    "SLIP":       "SLIP",
    "SPACE":      "SPC",
    "STOP":       "STOP",
    "SUITE":      "STE",
    "TRAILER":    "TRLR",
    "UNIT":       "UNIT",
    "UPPER":      "UPPR",
}

school_city_map = {
    'CINCINNATI CSD':'Cincinnati', 
    'DEER PARK CSD':'Cincinnati',
    'FINNEYTOWN LSD':'Cincinnati',
    'FOREST HILLS LSD':'Cincinnati',
    'INDIAN HILL EVSD':'Indian Hills',
    'LOCKLAND CSD': 'Cincinnati',
    'LOVELAND CSD':'Loveland', 
    'NORTHWEST LSD (HAMILTON CO.)':'Cincinnati',
    'MADEIRA CSD':'Madeira', 
    'MARIEMONT CSD':'Mariemont', 
    'MILFORD CSD':'Milford',
    'MOUNT HEALTHY CSD':'Cincinnati',
    'NORTH COLLEGE HILL CSD':'Cincinnati',
    'NORWOOD CSD':'Norwood', 
    'OAK HILLS LSD':'Cincinnati', 
    'PRINCETON CSD':'Cincinnati',
    'READING CSD':'Reading',
    'SOUTHWEST LSD (HAMILTON CO.)':'Harrison',
    'ST. BERNARD-ELMWOOD PLACE CSD':'Cincinnati',
    'SYCAMORE CSD':'Montgomery', 
    'THREE RIVERS LSD':'Cleves',
    'WINTON WOODS CSD':'Cincinnati',
    'WYOMING CSD':'Wyoming'
}

zip_code_map = {
    'CINCINNATI CSD':[45202, 45203, 45204, 45205, 45206, 45207, 45208, 45209, 45211, 45212, 45213, 45214, 
                      45215, 45216, 45217, 45219, 45220, 45223, 45224, 45225, 45226, 45227, 45229, 45230, 
                      45231, 45232, 45233, 45236, 45237, 45238, 45239, 45243, 45244, 45248], 
    'DEER PARK CSD': [45242,45236],
    'FINNEYTOWN LSD':[45232, 45231,45224, 45216,45215],
    'FOREST HILLS LSD':[45226, 45230, 45244, 45255],
    'INDIAN HILL EVSD':[45111, 45140, 45147, 45150, 45236, 45242, 45243, 45249],
    'LOCKLAND CSD':[45216,45215],
    'LOVELAND CSD':[45140, 45249], 
    'NORTH COLLEGE HILL CSD':[45224, 45231, 45239],
    'NORTHWEST LSD (HAMILTON CO.)':[45002, 45014, 45211, 45223, 45231, 45239, 45240, 45247, 45251, 45252],
    'NORWOOD CSD':[45207, 45208, 45209, 45212, 45229], 
    'MADEIRA CSD':[45227, 45236, 45243], 
    'MARIEMONT CSD':[45174, 45226, 45227, 45243], 
    'MILFORD CSD':[45140, 45147, 45150, 45174, 45243, 45244],
    'MOUNT HEALTHY CSD':[45218, 45231, 45240, 45251],
    'OAK HILLS LSD':[45002, 45051, 45204, 45211, 45233, 45238, 45247, 45248], 
    'PRINCETON CSD': [45040, 45069, 45215, 45240, 45241, 45242, 45246, 45249],
    'READING CSD':[45215, 45236, 45237],
    'SOUTHWEST LSD (HAMILTON CO.)':[45002, 45013, 45030, 45033, 45041, 45052, 45053],
    'ST. BERNARD-ELMWOOD PLACE CSD':[45216, 45217, 45229],
    'SYCAMORE CSD': [45140, 45236, 45241, 45242, 45249], 
    'THREE RIVERS LSD':[45001, 45002, 45052, 45233, 45248],
    'WINTON WOODS CSD': [45215, 45218, 45231, 45240, 45246],
    'WYOMING CSD':[45215, 45216] 
}

direction_map = {
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
    "NW": "NORTHWEST",
    "SW": "SOUTHWEST",
    "NE": "NORTHEAST",
    "SE": "SOUTHEAST",
    }

direction_map_tl = {i[1]:i[0] for i in direction_map.items()}

street_prefix_map = {
    # Saint / Sainte / Saints
    "ST":      "SAINT",
    "ST.":     "SAINT",
    "STE":     "SAINTE",
    "STE.":    "SAINTE",
    "STS":     "SAINTS",
    "STS.":    "SAINTS",

    # Spanish-language saints
    "SAN":     "SAN",
    "SANTA":   "SANTA",
    "SANTO":   "SANTO",
    "SANTOS":  "SANTOS",

    # Mount / Mountain
    "MT":      "MOUNT",
    "MT.":     "MOUNT",
    "MTN":     "MOUNTAIN",
    "MTN.":    "MOUNTAIN",

    # Fort
    "FT":      "FORT",
    "FT.":     "FORT",

    # Point
    "PT":      "POINT",
    "PT.":     "POINT",

    # Lake
    "LK":      "LAKE",
    "LK.":     "LAKE",

    # Peak / Park  (choose meaning at runtime if context matters)
    "PK":      "PEAK",
    "PK.":     "PEAK",

    # Port
    "PORT":    "PORT",
    "PRT":     "PORT",
}

