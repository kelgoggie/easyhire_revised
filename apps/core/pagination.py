"""Shared pagination + poor-match filtering helpers used across the card grids
(jobs for you, applications, applicants, all candidates).

The poor-match threshold mirrors the lowest non-poor tier in the match badge
template tag — anything under POOR_MATCH_THRESHOLD shows the red sad face.
"""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


POOR_MATCH_THRESHOLD = 60


def filter_poor_matches(items, request, score_key='score'):
    """Filter out items with score below POOR_MATCH_THRESHOLD.

    `show_poor=1` in the querystring keeps them. Items without a numeric score
    (e.g. incomplete jobseeker profiles) are always kept — they aren't poor,
    they just haven't been scored.

    Returns (visible_items, hidden_count, show_poor_flag).
    """
    show_poor = request.GET.get('show_poor') == '1'
    items = list(items)
    if show_poor:
        return items, 0, True

    visible, hidden = [], 0
    for it in items:
        score = it.get(score_key) if isinstance(it, dict) else getattr(it, score_key, None)
        if score is None or score >= POOR_MATCH_THRESHOLD:
            visible.append(it)
        else:
            hidden += 1
    return visible, hidden, False


def paginate(request, items, per_page=12, page_param='page'):
    """Wrap items in a Paginator page object. Accepts a list or queryset.

    Out-of-range pages are clamped (page < 1 → 1, page > num_pages → last page)
    to keep deep links robust.
    """
    paginator = Paginator(items, per_page)
    page_num = request.GET.get(page_param, 1)
    try:
        page = paginator.page(page_num)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    return page


def querystring_without(request, *params):
    """Return the current querystring minus the listed params, urlencoded.

    Used so pagination + toggle links preserve filters/search/sort while
    rewriting one specific param.
    """
    qd = request.GET.copy()
    for p in params:
        qd.pop(p, None)
    return qd.urlencode()
