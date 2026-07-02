from django import template

register = template.Library()


# (min_score, label, pill_classes, icon_color_class, emoji_type)
# emoji_type maps to an SVG smiley/frown variant rendered by the {% match_badge %} tag
# Palette note: Partial + Poor share the same amber palette as Decent so
# the lower tiers still read as "not the strongest fit" without dressing
# up as red-alarm negatives. Jobseekers get less discouraged; employers
# still see a distinct label + smiley for triage.
TIERS = [
    (98, 'Perfect Match',  'bg-green-500 text-white',                           'text-white',   'beam'),
    (90, 'Great Match',    'bg-teal text-white',                                'text-white',   'smile'),
    (80, 'Good Match',     'bg-teal/15 text-teal border border-teal/30',        'text-teal',    'smile'),
    (70, 'Decent Match',   'bg-amber/15 text-amber border border-amber/30',     'text-amber',   'mild'),
    (60, 'Partial Match',  'bg-amber/15 text-amber border border-amber/30',     'text-amber',   'meh'),
    (0,  'Poor Match',     'bg-amber/15 text-amber border border-amber/30',     'text-amber',   'sad'),
]


def _tier(score):
    """Return the tier tuple for a given numeric score."""
    if score is None:
        return None
    try:
        s = int(score)
    except (TypeError, ValueError):
        return None
    for min_score, label, pill, icon, emoji in TIERS:
        if s >= min_score:
            return (label, pill, icon, emoji)
    return TIERS[-1][1:]


_MONTH_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


@register.filter
def month_name(value):
    """Render a stored month value as 3-letter abbreviation (e.g. '2' -> 'Feb').

    Accepts: numeric strings ('2', '02'), ints (2), already-named months
    ('Feb', 'February'), or empty -> returns empty string.
    """
    if value in (None, '', 0):
        return ''
    try:
        n = int(str(value).lstrip('0') or '0')
        if 1 <= n <= 12:
            return _MONTH_ABBR[n]
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    for i, abbr in enumerate(_MONTH_ABBR):
        if i and (s.lower() == abbr.lower() or s.lower().startswith(abbr.lower())):
            return abbr
    return s


@register.inclusion_tag('jobseekers/_match_badge.html')
def match_badge(score, compact=False):
    """Render a match score badge.

    compact=True → just the smiley circle (no label pill).
    compact=False → full pill with smiley + label.
    """
    tier = _tier(score)
    if tier is None:
        return {'has_score': False}
    label, pill, icon, emoji = tier
    return {
        'has_score': True,
        'label': label,
        'pill_classes': pill,
        'icon_color': icon,
        'emoji': emoji,
        'compact': compact,
    }
