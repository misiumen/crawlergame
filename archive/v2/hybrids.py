"""Hybrid class system for CRAWL PROTOCOL."""
from features import get_feature


# Maps frozenset({class1, class2}) -> (hybrid_name, hybrid_feature_name, secondary_features)
_HYBRID_TABLE = {
    frozenset({"warrior", "mage"}): (
        "Battlemage",
        "Spellblade Strike",
        ["Arcane Bolt"],
    ),
    frozenset({"rogue", "engineer"}): (
        "Saboteur",
        "Explosive Backstab",
        ["Deploy Trap"],
    ),
    frozenset({"cleric", "warlock"}): (
        "Heretic",
        "Profane Miracle",
        ["Eldritch Bolt"],
    ),
    frozenset({"ranger", "psion"}): (
        "Seer Hunter",
        "Predicted Shot",
        ["Read Intent"],
    ),
    frozenset({"warrior", "cleric"}): (
        "Guardian",
        "Oathless Stand",
        ["Heal"],
    ),
    frozenset({"mage", "engineer"}): (
        "Inventor",
        "Arcane Device",
        ["Deploy Trap"],
    ),
}


def get_hybrid(primary, secondary):
    """
    Returns (hybrid_name, hybrid_feature, secondary_feature_list) or None.
    primary and secondary are class key strings (e.g. 'warrior').
    """
    key = frozenset({primary.lower(), secondary.lower()})
    result = _HYBRID_TABLE.get(key)
    if not result:
        return None
    hybrid_name, hybrid_feat_name, secondary_feat_names = result
    hybrid_feat = get_feature(hybrid_feat_name)
    secondary_feats = [f for f in (get_feature(n) for n in secondary_feat_names) if f]
    return hybrid_name, hybrid_feat, secondary_feats


def list_compatible(primary):
    """Return list of secondary class keys compatible with primary."""
    primary = primary.lower()
    compatible = []
    for key in _HYBRID_TABLE:
        if primary in key:
            other = [c for c in key if c != primary]
            compatible.extend(other)
    return compatible


def all_class_keys():
    """Return all class keys mentioned in hybrid table."""
    keys = set()
    for s in _HYBRID_TABLE:
        keys.update(s)
    return sorted(keys)
