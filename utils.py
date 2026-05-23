"""CRAWL PROTOCOL v2 - Dice utilities and helpers."""
import random
import re


def roll_die(sides):
    return random.randint(1, sides)


def roll_dice(count, sides):
    return sum(random.randint(1, sides) for _ in range(count))


def parse_dice(expr):
    """Parse '2d6+3' or '1d8' or '5' into an integer result."""
    expr = str(expr).strip().lower()
    total = 0
    for part in re.split(r'(?=[+-])', expr):
        part = part.strip()
        if not part:
            continue
        sign = 1
        if part.startswith('-'):
            sign = -1
            part = part[1:]
        elif part.startswith('+'):
            part = part[1:]
        m = re.match(r'^(\d+)d(\d+)$', part)
        if m:
            total += sign * roll_dice(int(m.group(1)), int(m.group(2)))
        else:
            try:
                total += sign * int(part)
            except ValueError:
                pass
    return total


def d20():
    return roll_die(20)


def ability_modifier(score):
    return (score - 10) // 2


def proficiency_bonus(level):
    from config import PROFICIENCY_BONUS
    return PROFICIENCY_BONUS.get(level, 2)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def stat_cost(score):
    from config import STAT_COST
    return STAT_COST.get(score, 99)


def wrap_text(text, max_chars):
    """Wrap a string to a list of lines no longer than max_chars."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current:
            if len(current) + 1 + len(word) <= max_chars:
                current += " " + word
            else:
                lines.append(current)
                current = word
        else:
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


def rating_label(rating):
    from config import RATING_LABELS
    label = RATING_LABELS[0][1]
    for threshold, name in RATING_LABELS:
        if rating >= threshold:
            label = name
    return label


def box_tier_color(tier):
    from config import (BOX_COPPER, BOX_SILVER, BOX_GOLD,
                        BOX_PLATINUM, BOX_TITANIUM, BOX_CLASS, BOX_SKILL)
    return {
        "Copper":   BOX_COPPER,
        "Silver":   BOX_SILVER,
        "Gold":     BOX_GOLD,
        "Platinum": BOX_PLATINUM,
        "Titanium": BOX_TITANIUM,
        "Class":    BOX_CLASS,
        "Skill":    BOX_SKILL,
    }.get(tier, BOX_COPPER)
