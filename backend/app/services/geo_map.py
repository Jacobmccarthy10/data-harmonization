"""US geography reference: regions, states, and major DMAs/cities.

A static reference table treated as a universal normalization layer (like
case-folding or state-abbreviation expansion). NOT client-specific.
Enables the market aligner to:

  - Recognize that 'Mid-Atlantic Operating Area' geographically contains
    Virginia, Maryland, and Delaware
  - Recognize that 'Western NY Operating Area' contains the cities
    Buffalo, Rochester, Syracuse, etc. (all in NY)
  - Match a client region to a Discover total at the next-broadest level
    when no 1:1 sibling exists
  - Sum multiple Discover sub-markets into a synthetic aggregate when the
    client region clearly contains them

Coverage is the major US retail markets that appear in NIQ Discover labels
(Buffalo TA, Atlanta TA, Dallas-Ft Worth TA, ...). The table is meant to be
extended generically; nothing here depends on any specific retailer.
"""
from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# States — name <-> two-letter code (and a few common variants)
# ---------------------------------------------------------------------------

STATES: Dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN",
    "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES: Dict[str, str] = {code: name for name, code in STATES.items()}
STATE_ABBR_ALIASES: Dict[str, str] = {
    **{c.lower(): c for c in STATE_CODES},
    "nyc": "NY",
    "dc": "DC",
    "calif": "CA", "cali": "CA",
    "penn": "PA", "penna": "PA",
    "mass": "MA", "conn": "CT", "wash": "WA", "ariz": "AZ", "tex": "TX",
}

# ---------------------------------------------------------------------------
# Regions — common business-region groupings used in retail planning.
# ---------------------------------------------------------------------------

REGIONS: Dict[str, FrozenSet[str]] = {
    "northeast": frozenset({"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"}),
    "mid-atlantic": frozenset({"NY", "NJ", "PA", "DE", "MD", "DC", "VA", "WV"}),
    "southeast": frozenset({"FL", "GA", "SC", "NC", "TN", "AL", "MS", "AR", "LA", "KY"}),
    "midwest": frozenset({"OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"}),
    "great lakes": frozenset({"OH", "MI", "IN", "IL", "WI", "MN", "PA", "NY"}),
    "plains": frozenset({"ND", "SD", "NE", "KS", "IA", "MO", "MN"}),
    "south central": frozenset({"TX", "OK", "AR", "LA"}),
    "southwest": frozenset({"TX", "OK", "NM", "AZ"}),
    "mountain": frozenset({"MT", "ID", "WY", "CO", "UT", "NV", "AZ", "NM"}),
    "west": frozenset({"WA", "OR", "CA", "NV", "ID", "MT", "WY", "UT", "CO",
                       "AZ", "NM", "AK", "HI"}),
    "west coast": frozenset({"CA", "OR", "WA"}),
    "pacific": frozenset({"CA", "OR", "WA", "AK", "HI"}),
    "pacific northwest": frozenset({"WA", "OR", "ID"}),
    "central": frozenset({"IL", "WI", "MN", "IA", "MO", "IN", "OH", "MI"}),
    "south": frozenset({"FL", "GA", "SC", "NC", "TN", "AL", "MS", "AR", "LA",
                        "KY", "TX", "OK", "VA", "WV"}),
    "north": frozenset({"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA",
                        "OH", "MI", "WI", "MN", "ND", "SD", "MT", "WA"}),
    "east": frozenset({"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA",
                        "DE", "MD", "VA", "NC", "SC", "GA", "FL", "DC"}),
    "national": frozenset(STATE_CODES.keys()),
    "national account": frozenset(STATE_CODES.keys()),
    "total": frozenset(STATE_CODES.keys()),
    "total us": frozenset(STATE_CODES.keys()),
    "us": frozenset(STATE_CODES.keys()),
    "all us": frozenset(STATE_CODES.keys()),
    # Common sub-regions named in retail data
    "florida peninsula": frozenset({"FL"}),
    "florida": frozenset({"FL"}),
    "carolinas": frozenset({"NC", "SC"}),
    "tristate": frozenset({"NY", "NJ", "CT"}),
    "tri state": frozenset({"NY", "NJ", "CT"}),
    "new england": frozenset({"ME", "NH", "VT", "MA", "RI", "CT"}),
    "deep south": frozenset({"AL", "MS", "GA", "LA", "SC"}),
    "appalachia": frozenset({"WV", "KY", "TN", "VA"}),
    "rust belt": frozenset({"OH", "MI", "IN", "IL", "WI", "PA", "WV"}),
    "sun belt": frozenset({"AZ", "CA", "FL", "GA", "NV", "NM", "NC", "SC", "TX"}),
    "rocky mountain": frozenset({"MT", "ID", "WY", "CO", "UT"}),
}

# Compass / sub-state qualifiers that recur in client labels.
# A label like "Western NY Operating Area" => qualifier="western" + state="NY".
COMPASS_PREFIXES: Set[str] = {
    "western", "eastern", "northern", "southern", "central",
    "north", "south", "east", "west", "mid", "upper", "lower",
    "north central", "south central", "northwest", "northeast",
    "southwest", "southeast",
}

# ---------------------------------------------------------------------------
# DMAs / cities -> state code. Only the cities that appear in NIQ Discover
# market labels we have seen; extend generically as new ones come in.
# ---------------------------------------------------------------------------

DMAS: Dict[str, str] = {
    "albany": "NY", "albany syracuse": "NY",
    "atlanta": "GA",
    "baltimore": "MD",
    "birmingham": "AL",
    "boise": "ID",
    "boston": "MA",
    "buffalo": "NY",
    "champaign peoria": "IL",
    "charleston": "WV",  # also SC; NIQ uses Lexington-Charleston for WV
    "charlotte": "NC",
    "chicago": "IL",
    "cincinnati": "OH",
    "cleveland": "OH",
    "columbus": "OH", "columbus oh": "OH",
    "dallas ft worth": "TX", "dallas fort worth": "TX", "dallas": "TX",
    "denver": "CO",
    "des moines cedar rapids": "IA", "des moines": "IA",
    "detroit": "MI",
    "fresno bakersfield": "CA", "fresno": "CA", "bakersfield": "CA",
    "ft myers": "FL", "fort myers": "FL", "palm beach ft myers": "FL",
    "grand rapids kalamazoo": "MI", "grand rapids": "MI", "kalamazoo": "MI",
    "hartford providence": "CT", "hartford": "CT", "providence": "RI",
    "harrisburg": "PA",
    "houston": "TX",
    "indianapolis": "IN",
    "jacksonville": "FL",
    "kansas city": "MO",
    "knoxville": "TN",
    "lakeland": "FL",
    "las vegas": "NV",
    "lexington": "KY", "lexington charleston": "KY",
    "los angeles": "CA", "la": "CA",
    "louisville": "KY",
    "memphis": "TN",
    "miami": "FL", "miami ft lauderdale": "FL", "ft lauderdale": "FL",
    "milwaukee": "WI",
    "minneapolis": "MN", "minneapolis st paul": "MN",
    "mobile": "AL",
    "nashville": "TN",
    "new orleans": "LA",
    "new york": "NY", "new york city": "NY",
    "oklahoma city": "OK",
    "omaha wichita": "NE", "omaha": "NE", "wichita": "KS",
    "orlando": "FL", "orlando daytona beach": "FL", "daytona": "FL",
    "philadelphia": "PA",
    "phoenix": "AZ",
    "pittsburgh": "PA",
    "portland": "OR", "portland me burlington vt": "ME", "burlington": "VT",
    "raleigh": "NC", "raleigh durham": "NC",
    "richmond": "VA",
    "rochester": "NY",
    "s carolina": "SC", "south carolina": "SC", "sc": "SC",
    "sacramento": "CA",
    "salt lake": "UT", "salt lake city": "UT", "salt lake boise": "UT",
    "san diego": "CA",
    "san francisco": "CA", "san fran": "CA", "san fran oakland sj": "CA",
    "san jose": "CA", "oakland": "CA",
    "savannah": "GA",
    "seattle": "WA", "seattle tacoma": "WA", "seattle tacoma wa": "WA",
    "south west texas": "TX", "southwest texas": "TX",
    "southern tier": "NY",   # NIQ market name; covers southern NY counties
    "spokane": "WA",
    "st louis": "MO", "saint louis": "MO",
    "syracuse": "NY",
    "tampa": "FL", "tampa st petersburg": "FL", "st petersburg": "FL",
    "toledo ft wayne": "OH", "toledo": "OH", "ft wayne": "IN", "fort wayne": "IN",
    "washington dc": "DC", "washington": "DC",
    "virginia maryland": "VA",  # NIQ market name; we pick a primary state
}

# Sub-state qualifiers that pair with a state to define a region within it
# (e.g. "Western NY" -> upstate NY DMAs). Maps (compass, state_code) ->
# set of canonical DMA tokens that geographically belong to that region.
SUBSTATE_DMAS: Dict[Tuple[str, str], FrozenSet[str]] = {
    ("western", "NY"): frozenset({"buffalo", "rochester", "syracuse",
                                  "southern tier", "albany syracuse"}),
    ("upstate", "NY"): frozenset({"buffalo", "rochester", "syracuse",
                                  "southern tier", "albany syracuse", "albany"}),
    ("central", "NY"): frozenset({"syracuse", "albany syracuse"}),
    ("eastern", "NY"): frozenset({"new york", "albany"}),
    ("northern", "NY"): frozenset({"albany syracuse", "albany"}),
    ("southern", "NY"): frozenset({"new york", "southern tier"}),
    ("western", "PA"): frozenset({"pittsburgh"}),
    ("eastern", "PA"): frozenset({"philadelphia", "harrisburg"}),
    ("southern", "CA"): frozenset({"los angeles", "san diego"}),
    ("northern", "CA"): frozenset({"san francisco", "san fran oakland sj",
                                   "sacramento"}),
    ("central", "CA"): frozenset({"fresno bakersfield", "fresno", "bakersfield"}),
}

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

_NORM_RE = re.compile(r"[A-Za-z][A-Za-z]*")


def _label_tokens(label: str) -> List[str]:
    return [t.lower() for t in _NORM_RE.findall(label or "")]


def _label_norm(label: str) -> str:
    return " ".join(_label_tokens(label))


def states_in_label(label: str) -> Set[str]:
    """All state codes mentioned in a label, via full name or abbreviation."""
    if not label:
        return set()
    found: Set[str] = set()
    tokens = _label_tokens(label)
    norm = " ".join(tokens)
    # Multi-word state names first.
    for name, code in STATES.items():
        if " " in name and name in norm:
            found.add(code)
    # Single-word state names and abbreviations.
    for t in tokens:
        if t in STATES:
            found.add(STATES[t])
        elif t in STATE_ABBR_ALIASES:
            found.add(STATE_ABBR_ALIASES[t])
    return found


def regions_in_label(label: str) -> List[str]:
    """Named regions mentioned in a label, matched on whole-word boundaries.

    Whole-word matching matters: 'west' must NOT match inside 'midwest',
    'central' must NOT match inside any random word, etc.
    """
    norm = _label_norm(label)
    if not norm:
        return []
    hits: List[str] = []
    for r in REGIONS:
        if re.search(rf"(?<!\w){re.escape(r)}(?!\w)", norm):
            hits.append(r)
    return hits


def region_states(region_name: str) -> FrozenSet[str]:
    return REGIONS.get(region_name.lower().strip(), frozenset())


def dmas_in_label(label: str) -> List[str]:
    """Major city/DMA names mentioned in a label, whole-word matched.

    Longer DMA names are matched first so 'boise' doesn't steal from
    'salt lake boise'. Whole-word matching prevents 'la' from matching
    inside 'walmart' or 'orlando'.
    """
    norm = _label_norm(label)
    if not norm:
        return []
    hits: List[str] = []
    for dma in sorted(DMAS, key=len, reverse=True):
        if dma in " ".join(hits):
            continue
        if re.search(rf"(?<!\w){re.escape(dma)}(?!\w)", norm):
            hits.append(dma)
    return hits


def state_for_dma(dma: str) -> Optional[str]:
    return DMAS.get(dma.lower().strip())


def expand_label_to_state_set(label: str) -> Set[str]:
    """Every state a label refers to, via region OR explicit state OR DMA."""
    states: Set[str] = set()
    states.update(states_in_label(label))
    for r in regions_in_label(label):
        states.update(REGIONS[r])
    for dma in dmas_in_label(label):
        st = state_for_dma(dma)
        if st:
            states.add(st)

    # Compass-qualified state region: "Western NY", "Southern California".
    tokens = _label_tokens(label)
    for i, t in enumerate(tokens):
        if t not in COMPASS_PREFIXES:
            continue
        for j in (i + 1, i + 2):  # accommodate "south central tx"
            if j >= len(tokens):
                break
            tk = tokens[j]
            state_code = (STATES.get(tk) or STATE_ABBR_ALIASES.get(tk))
            if not state_code:
                continue
            key = (t, state_code)
            sub = SUBSTATE_DMAS.get(key)
            if sub:
                # Convert DMA list to states (all in the parent state).
                for dma in sub:
                    s = state_for_dma(dma)
                    if s:
                        states.add(s)
            else:
                states.add(state_code)
    return states


def dmas_for_label_region(label: str) -> List[str]:
    """If the label is a compass-qualified state region (e.g. 'Western NY
    Operating Area'), return the DMA names that geographically belong to
    that sub-state region. Used for many-to-one rollups.
    """
    tokens = _label_tokens(label)
    for i, t in enumerate(tokens):
        if t not in COMPASS_PREFIXES:
            continue
        for j in (i + 1, i + 2):
            if j >= len(tokens):
                break
            tk = tokens[j]
            state_code = (STATES.get(tk) or STATE_ABBR_ALIASES.get(tk))
            if state_code and (t, state_code) in SUBSTATE_DMAS:
                return list(SUBSTATE_DMAS[(t, state_code)])
    return []


def label_geographic_footprint(label: str) -> Set[str]:
    """States a label covers — for testing whether one label is contained
    inside another. 'Mid-Atlantic Operating Area' -> {VA, MD, DC, ...}.
    """
    return expand_label_to_state_set(label)
