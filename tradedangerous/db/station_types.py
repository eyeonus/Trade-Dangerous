"""
Canonical station type registry for Trade Dangerous.

Single source of truth for:
- internal type_id constants (0–15)
- external (Spansh) station type string mapping
- classification sets (fleet carriers, settlements, planetary)
- Y/N/? state helpers
"""

# ---------------------------------------------------------------------------
# Internal type_id constants
# 0 is reserved for unknown / missing / unrecognised.
# Remaining values follow the Spansh station-type enum order.
# ---------------------------------------------------------------------------

UNKNOWN                     = 0
ASTEROID_BASE               = 1
CORIOLIS_STARPORT           = 2
DOCKABLE_PLANET_STATION     = 3
DODEC_STARPORT              = 4
DRAKE_CLASS_CARRIER         = 5
MEGA_SHIP                   = 6
OCELLUS_STARPORT            = 7
ORBIS_STARPORT              = 8
OUTPOST                     = 9
PLANETARY_CONSTRUCTION_DEPOT = 10
PLANETARY_OUTPOST           = 11
PLANETARY_PORT              = 12
SETTLEMENT                  = 13
SPACE_CONSTRUCTION_DEPOT    = 14
SURFACE_SETTLEMENT          = 15

# ---------------------------------------------------------------------------
# Display names (for debugging, docs, and tests)
# ---------------------------------------------------------------------------

DISPLAY_NAMES: dict[int, str] = {
    UNKNOWN:                     "Unknown",
    ASTEROID_BASE:               "Asteroid Base",
    CORIOLIS_STARPORT:           "Coriolis Starport",
    DOCKABLE_PLANET_STATION:     "Dockable Planet Station",
    DODEC_STARPORT:              "Dodec Starport",
    DRAKE_CLASS_CARRIER:         "Drake-Class Carrier",
    MEGA_SHIP:                   "Mega Ship",
    OCELLUS_STARPORT:            "Ocellus Starport",
    ORBIS_STARPORT:              "Orbis Starport",
    OUTPOST:                     "Outpost",
    PLANETARY_CONSTRUCTION_DEPOT: "Planetary Construction Depot",
    PLANETARY_OUTPOST:           "Planetary Outpost",
    PLANETARY_PORT:              "Planetary Port",
    SETTLEMENT:                  "Settlement",
    SPACE_CONSTRUCTION_DEPOT:    "Space Construction Depot",
    SURFACE_SETTLEMENT:          "Surface Settlement",
}

# ---------------------------------------------------------------------------
# External string → internal type_id
# Keys are lowercased and stripped for normalisation.
# ---------------------------------------------------------------------------

_EXTERNAL_TO_TYPE_ID: dict[str, int] = {
    "asteroid base":               ASTEROID_BASE,
    "coriolis starport":           CORIOLIS_STARPORT,
    "dockable planet station":     DOCKABLE_PLANET_STATION,
    "dodec starport":              DODEC_STARPORT,
    "drake-class carrier":         DRAKE_CLASS_CARRIER,
    "mega ship":                   MEGA_SHIP,
    "ocellus starport":            OCELLUS_STARPORT,
    "orbis starport":              ORBIS_STARPORT,
    "outpost":                     OUTPOST,
    "planetary construction depot": PLANETARY_CONSTRUCTION_DEPOT,
    "planetary outpost":           PLANETARY_OUTPOST,
    "planetary port":              PLANETARY_PORT,
    "settlement":                  SETTLEMENT,
    "space construction depot":    SPACE_CONSTRUCTION_DEPOT,
    "surface settlement":          SURFACE_SETTLEMENT,
    # Observed alias: hyphen sometimes omitted
    "drake class carrier":         DRAKE_CLASS_CARRIER,
}


def station_type_id_from_external(type_name) -> int:
    """Map a Spansh station type string to an internal type_id.

    Returns UNKNOWN for None, non-string, or unrecognised input.
    Normalises by stripping whitespace and lowercasing.
    """
    if not isinstance(type_name, str):
        return UNKNOWN
    return _EXTERNAL_TO_TYPE_ID.get(type_name.strip().lower(), UNKNOWN)


# ---------------------------------------------------------------------------
# Semantic classification sets
# ---------------------------------------------------------------------------

FLEET_CARRIER_TYPE_IDS: frozenset[int] = frozenset({
    DRAKE_CLASS_CARRIER,
})

SETTLEMENT_TYPE_IDS: frozenset[int] = frozenset({
    PLANETARY_CONSTRUCTION_DEPOT,
    SETTLEMENT,
    SURFACE_SETTLEMENT,
})

# Reference set for import mapping and documentation.
# Not used as the authoritative planetary filter — Station.planetary is.
PLANETARY_BY_TYPE_IDS: frozenset[int] = frozenset({
    DOCKABLE_PLANET_STATION,
    PLANETARY_CONSTRUCTION_DEPOT,
    PLANETARY_OUTPOST,
    PLANETARY_PORT,
    SETTLEMENT,
    SURFACE_SETTLEMENT,
})

# ---------------------------------------------------------------------------
# Y/N/? state helpers
# ---------------------------------------------------------------------------

def fleet_carrier_state(type_id: int) -> str:
    """Return Y/N/? fleet carrier classification for a type_id.

    Y — known fleet carrier (Drake-Class Carrier)
    N — known non-fleet-carrier
    ? — type unknown (type_id == UNKNOWN)
    """
    if type_id == UNKNOWN:
        return "?"
    return "Y" if type_id in FLEET_CARRIER_TYPE_IDS else "N"


def settlement_state(type_id: int) -> str:
    """Return Y/N/? settlement classification for a type_id.

    Y — settlement / surface facility
    N — known non-settlement station
    ? — type unknown (type_id == UNKNOWN)
    """
    if type_id == UNKNOWN:
        return "?"
    return "Y" if type_id in SETTLEMENT_TYPE_IDS else "N"
