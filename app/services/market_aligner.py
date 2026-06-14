"""Generic, token-based market alignment between client and Discover labels.

No client-specific or retailer-specific hardcoding. The matcher generates
multiple normalized candidate forms of each label (raw, customer-prefixed,
suffix-stripped, state-expanded) and scores every cross-pair with a
token-set fuzzy ratio. The best-scoring pair above the configured threshold
wins, with the match basis surfaced so the dashboard can distinguish a clean
match from a partial one.

State expansion (e.g. "NY" <-> "New York") uses a universal US-state alias
table -- a generic normalization layer like case-folding, not data-specific
configuration.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from ..utils.text import is_total_like_market, norm_value
from . import geo_map

# Universal US state alias map. Treated as a normalization layer (like
# case-folding) -- expands two-letter abbreviations and the special-case
# "NYC" so that token-set fuzzy matching can recognize "NY" and "New York"
# as the same place. Not specific to any client.
US_STATE_ALIASES: Dict[str, str] = {
    "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas",
    "ca": "california", "co": "colorado", "ct": "connecticut", "de": "delaware",
    "fl": "florida", "ga": "georgia", "hi": "hawaii", "id": "idaho",
    "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas",
    "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland",
    "ma": "massachusetts", "mi": "michigan", "mn": "minnesota", "ms": "mississippi",
    "mo": "missouri", "mt": "montana", "ne": "nebraska", "nv": "nevada",
    "nh": "new hampshire", "nj": "new jersey", "nm": "new mexico",
    "ny": "new york", "nc": "north carolina", "nd": "north dakota",
    "oh": "ohio", "ok": "oklahoma", "or": "oregon", "pa": "pennsylvania",
    "ri": "rhode island", "sc": "south carolina", "sd": "south dakota",
    "tn": "tennessee", "tx": "texas", "ut": "utah", "vt": "vermont",
    "va": "virginia", "wa": "washington", "wv": "west virginia",
    "wi": "wisconsin", "wy": "wyoming", "dc": "district of columbia",
    "nyc": "new york",
}

# Generic market-label suffixes / connective words to drop. These are not
# client- or retailer-specific -- they appear across retail data (TA = Total
# Area / Trade Area, "Operating Area" on the planning side, etc.).
_GENERIC_TOKENS = {
    "ta", "tac", "trade", "area", "areas", "operating", "operation",
    "region", "regions", "zone", "zones", "district", "districts",
    "account", "accounts", "market", "markets", "geography", "geo",
    "division", "divisions", "territory", "territories", "channel",
    "channels", "planning", "sales", "remaining", "rem", "subregion",
    "the", "of", "and",
}

# Directional / compass tokens that should not anchor a match on their own.
# "South Region" alone cannot identify any Discover market -- without
# knowing which states make up the client's "south", matching it to "S
# Carolina TA" or "South-West Texas TA" is a false friend. Stripped from
# both sides before the fuzzy comparison so the score reflects only
# substantive tokens.
_DIRECTIONAL_TOKENS = {
    "north", "south", "east", "west", "central", "mid", "midwest",
    "midatlantic", "northern", "southern", "eastern", "western",
    "northeast", "northwest", "southeast", "southwest", "upper", "lower",
}

_TOTAL_KEYWORDS = {"total", "all", "national", "overall", "combined",
                   "corporate", "enterprise", "company", "companywide",
                   "customer", "account"}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")


def _tokens(label: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(label or "")]


def _expand_states(tokens: List[str]) -> List[str]:
    out: List[str] = []
    for t in tokens:
        out.append(t)
        if t in US_STATE_ALIASES:
            out.extend(US_STATE_ALIASES[t].split())
    return out


def _strip_generic(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in _GENERIC_TOKENS]


def _strip_directional(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in _DIRECTIONAL_TOKENS]


def _weak_token(t: str) -> bool:
    """A token that should not anchor a match on its own."""
    return (t in _GENERIC_TOKENS or t in _DIRECTIONAL_TOKENS
            or t in _TOTAL_KEYWORDS or len(t) <= 1)


def _strip_customer(tokens: List[str], customer_tokens: List[str]) -> List[str]:
    cust = set(customer_tokens)
    return [t for t in tokens if t not in cust]


def _join(tokens: List[str]) -> str:
    return " ".join(tokens).strip()


def _has_total(tokens: List[str]) -> bool:
    return any(t in _TOTAL_KEYWORDS for t in tokens)


@dataclass
class MarketMatch:
    client: str
    discover: Optional[str]
    score: float
    basis: str  # exact | customer-prefix | state-expanded | total-rollup | geo-rollup | aggregate-overlap | none
    matched: bool
    matched_with_caveat: bool
    # For geo-rollup: the Discover sub-markets that were summed into the
    # synthetic aggregate. Empty for 1:1 matches.
    rollup_components: Tuple[str, ...] = ()


def _candidates(label: str, customer_tokens: List[str]) -> List[Tuple[str, str]]:
    """Generate normalized candidate forms of a market label.

    Always strips generic + directional tokens from the "core" forms, so
    directional words like 'south' or 'west' cannot anchor a match on their
    own. No client- or retailer-specific logic.
    """
    base = _expand_states(_tokens(label))
    if not base:
        return []
    variants: List[Tuple[str, str]] = []

    def add(tokens: List[str], kind: str) -> None:
        text = _join(tokens)
        if text and (text, kind) not in variants:
            variants.append((text, kind))

    no_cust = _strip_customer(base, customer_tokens)
    # "core" = strip customer + generic suffixes + directional words. This is
    # the strongest form for fuzzy matching -- only city/state-like tokens
    # survive.
    core = _strip_directional(_strip_generic(no_cust))
    no_generic = _strip_directional(_strip_generic(base))

    add(base, "raw")
    add(no_cust, "no-customer")
    add(no_generic, "no-generic")
    add(core, "core")
    add(customer_tokens + no_cust, "customer-prefix")
    add(customer_tokens + core, "customer-prefix-core")
    return variants


def _core_tokens(label: str, customer_tokens: List[str]) -> List[str]:
    """Distinctive tokens left after stripping customer / generic / directional."""
    base = _expand_states(_tokens(label))
    return _strip_directional(_strip_generic(_strip_customer(base, customer_tokens)))


def _broadest_total(labels: List[str]) -> Optional[str]:
    """Pick the broadest total-like market (shortest by significant tokens).

    Generic heuristic: 'Walmart Total US TA' (3 strong tokens) wins over
    'Walmart NHM Total US TA' (4) and 'Walmart SC Total US TA' (4).
    """
    totals = [l for l in labels if is_total_like_market(l)]
    if not totals:
        return None
    def strong_len(l: str) -> int:
        return len([t for t in _tokens(l) if not _weak_token(t)])
    return min(totals, key=lambda l: (strong_len(l), len(_tokens(l))))


def align_markets(
    client_markets: List[str],
    discover_markets: List[str],
    customer: Optional[str] = None,
    high_threshold: int = 88,
    caveat_threshold: int = 78,
) -> Tuple[Dict[str, str], List[MarketMatch], List[str]]:
    """Align client market labels to discover market labels generically.

    Three-pass algorithm:
        1. Total-to-total: pair the broadest client total ("National Account",
           "Customer Total", ...) with the broadest Discover total. Locks the
           Discover total before greedy fuzzy can claim it.
        2. Greedy fuzzy across the remaining client x discover pairs, scored
           on every candidate-variant cross-product. Highest-score pairs
           claim their Discover target first.
        3. Rejection: a fuzzy match is accepted only if the client and the
           Discover side share at least one *core* token (after stripping
           customer / generic / directional words). This filters out false
           friends like "South Region" <-> "South-West Texas TA" where only
           a directional word overlaps.
    """
    matches_by_client: Dict[str, MarketMatch] = {}
    warnings: List[str] = []
    if not client_markets or not discover_markets:
        return {}, [], warnings

    customer_tokens = _expand_states(_tokens(customer or ""))
    used: set = set()
    mapping: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Pass 1: totals first.
    # ------------------------------------------------------------------
    client_totals = [c for c in client_markets if is_total_like_market(c)]
    if client_totals:
        broadest_disc = _broadest_total(discover_markets)
        if broadest_disc:
            # Pick the broadest client total too (shortest by strong tokens).
            broadest_client = min(
                client_totals,
                key=lambda c: (len([t for t in _tokens(c) if not _weak_token(t)]),
                               len(_tokens(c))),
            )
            mapping[broadest_client] = broadest_disc
            used.add(broadest_disc)
            matches_by_client[broadest_client] = MarketMatch(
                broadest_client, broadest_disc, 1.0, "total-rollup", True, False)

    # ------------------------------------------------------------------
    # Pass 2: greedy fuzzy on the remaining client markets.
    # ------------------------------------------------------------------
    discover_variants: Dict[str, List[Tuple[str, str]]] = {
        d: _candidates(d, customer_tokens) for d in discover_markets
    }
    scored: List[Tuple[float, str, str, str]] = []
    for c in client_markets:
        if c in matches_by_client:
            continue
        client_variants = _candidates(c, customer_tokens)
        best_score = 0.0
        best_d = None
        best_basis = "none"
        for d in discover_markets:
            if d in used:
                continue
            for cf, ck in client_variants:
                for df, dk in discover_variants[d]:
                    s = fuzz.token_set_ratio(cf, df)
                    if s > best_score:
                        best_score = s
                        best_d = d
                        best_basis = _basis_label(ck, dk, c, d)
        scored.append((best_score, c, best_d, best_basis))

    scored.sort(key=lambda t: -t[0])

    for score, c, d, basis in scored:
        matched, caveat, final_basis = False, False, "none"
        if d is not None and d not in used and score >= caveat_threshold:
            # Residual-overlap sanity check: at least one core (city/state-
            # like) token must be shared between the two sides. Filters
            # false friends driven only by directional words.
            client_core = set(_core_tokens(c, customer_tokens))
            disc_core = set(_core_tokens(d, customer_tokens))
            if client_core & disc_core:
                mapping[c] = d
                used.add(d)
                matched = True
                caveat = score < high_threshold
                final_basis = basis
                if caveat:
                    warnings.append(
                        f"Client market '{c}' fuzzy-matched to Discover market "
                        f"'{d}' (score {score / 100:.2f}, basis: {final_basis}). "
                        "Treated as a matched_with_caveat alignment.")
        matches_by_client[c] = MarketMatch(
            c, d if matched else None, float(score) / 100.0,
            final_basis, matched, caveat)

    # ------------------------------------------------------------------
    # Pass 3: geo-rollup. For client markets still unmatched, use the geo
    # map to identify Discover sub-markets that geographically belong to
    # the client region and sum them into a synthetic aggregate.
    # ------------------------------------------------------------------
    for c in client_markets:
        existing = matches_by_client.get(c)
        if existing and existing.matched:
            continue
        client_states = geo_map.expand_label_to_state_set(c)
        if not client_states:
            continue
        # Find Discover markets that fall inside the client region:
        # either explicitly mention a state in client_states or contain a
        # DMA token whose state is in client_states. Exclude already used,
        # exclude total-like (totals over-aggregate), exclude markets that
        # are themselves super-sets of the client region (e.g. don't pick
        # "Total NY" when the client said "Western NY" — Total NY > Western NY).
        components: List[str] = []
        for d in discover_markets:
            if d in used:
                continue
            if is_total_like_market(d):
                continue
            d_states = geo_map.expand_label_to_state_set(d)
            if not d_states:
                continue
            # Sub-market belongs to client region if its states are a non-empty
            # subset of the client region.
            if d_states.issubset(client_states) and len(d_states) <= len(client_states):
                # Optional sub-state filter: for compass-qualified regions
                # like 'Western NY', restrict to the DMAs the geo map says
                # belong to that sub-region.
                allowed_dmas = geo_map.dmas_for_label_region(c)
                if allowed_dmas:
                    d_dmas = geo_map.dmas_in_label(d)
                    if not (set(d_dmas) & set(allowed_dmas)):
                        continue
                components.append(d)
        if components:
            synth = (
                f"{c}  (rollup of: "
                + ", ".join(sorted(components))
                + ")"
            )
            mapping[c] = synth
            for d in components:
                used.add(d)
            matches_by_client[c] = MarketMatch(
                c, synth, 0.85, "geo-rollup", True, True,
                rollup_components=tuple(sorted(components)))
            warnings.append(
                f"Client market '{c}' aligned to a sum of {len(components)} "
                f"Discover sub-markets ({', '.join(sorted(components))}) via "
                "the US geography map. Treated as a matched_with_caveat alignment.")

    # Ensure every client market has an entry, even if untouched.
    for c in client_markets:
        if c not in matches_by_client:
            matches_by_client[c] = MarketMatch(c, None, 0.0, "none", False, False)

    return mapping, list(matches_by_client.values()), warnings


def _basis_label(client_kind: str, discover_kind: str, c: str, d: str) -> str:
    if norm_value(c) == norm_value(d):
        return "exact"
    if "customer" in client_kind or "customer" in discover_kind:
        return "customer-prefix"
    if "core" in client_kind or "no-generic" in client_kind:
        return "stripped-suffix"
    if _has_total(_tokens(c)) and _has_total(_tokens(d)):
        return "total-rollup"
    return "fuzzy"
