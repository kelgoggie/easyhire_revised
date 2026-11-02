from django import template

register = template.Library()


# Scores below this never surface to jobseekers or employers — PESO decided
# a sub-65 match isn't a meaningful recommendation. apps.matching.engine's
# get_ranked_jobs()/get_ranked_jobseekers() enforce this at the data layer;
# admin audit views intentionally bypass it (PESO staff need full visibility).
VISIBILITY_THRESHOLD = 65

# (min_score, label, pill_classes, icon_color_class, emoji_type)
# emoji_type maps to an SVG smiley/frown variant rendered by the {% match_badge %} tag
# Only the top two tiers are ever shown to jobseekers/employers (anything
# below VISIBILITY_THRESHOLD is filtered out before it reaches them). The
# 'Below Threshold' tier still renders correctly wherever a raw score sneaks
# through on an admin-only page — those are PESO's internal audit views.
TIERS = [
    (85, 'Highly Recommended', 'bg-emerald-500 text-white',                        'text-white',    'beam'),
    (65, 'Recommended',        'bg-teal/15 text-teal border border-teal/30',       'text-teal',     'smile'),
    (0,  'Below Threshold',    'bg-gray-100 text-gray-500 border border-gray-300', 'text-gray-400', 'sad'),
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
def match_badge(score, compact=False, show_score=False):
    """Render a match score badge.

    compact=True → just the smiley circle (no label pill).
    compact=False → full pill with smiley + label (or the numeric score,
    see show_score).
    show_score=True → pill text is the numeric score ("92%") instead of the
    tier label ("Highly Recommended") — same tier background color either
    way. Used on admin pages, where PESO staff want the actual number
    rather than the jobseeker/employer-facing descriptor.
    """
    tier = _tier(score)
    if tier is None:
        return {'has_score': False}
    label, pill, icon, emoji = tier
    return {
        'has_score': True,
        'label': label,
        'score': int(score),
        'show_score': show_score,
        'pill_classes': pill,
        'icon_color': icon,
        'emoji': emoji,
        'compact': compact,
    }
