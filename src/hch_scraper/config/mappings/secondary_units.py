apt_head_works = {
    "#",
    "APT", 
    "UNIT", 
    "STE", 
    "SUITE", 
    "ROOM", 
    "RM"
    }

spelled_out_numbers = {
    # cardinal numbers
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    # ordinal numbers
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "thirtieth", "fortieth", "fiftieth",
    "sixtieth", "seventieth", "eightieth", "ninetieth",
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
