from django import template

register = template.Library()


# (min_score, label, pill_classes, icon_color_class, emoji_type)
# emoji_type maps to an SVG smiley/frown variant rendered by the {% match_badge %} tag
TIERS = [
    (98, 'Perfect Match',  'bg-green-500 text-white',           'text-white',         'beam'),
    (90, 'Great Match',    'bg-teal text-white',                'text-white',         'smile'),
    (80, 'Good Match',     'bg-teal/15 text-teal border border-teal/30',         'text-teal',          'smile'),
    (70, 'Decent Match',   'bg-amber/15 text-amber border border-amber/30',      'text-amber',         'mild'),
    (60, 'Partial Match',  'bg-orange-100 text-orange-500 border border-orange-200', 'text-orange-500', 'meh'),
    (0,  'Poor Match',     'bg-red-50 text-red-400 border border-red-200',      'text-red-400',       'sad'),
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
