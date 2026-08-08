"""Employer-side smart back-link helper.

Same shape as `admin_nav.smart_back` but recognises employer routes
(`/employers/…`) instead of `/admin-panel/`. Usage:

    {% load employer_nav %}
    {% smart_back "/employers/all_candidates/" "Back to All Candidates" as back %}
    <a href="{{ back.url }}">... {{ back.label }}</a>

If the Referer is a same-origin employer URL we recognise, the returned
dict uses it and picks a natural label from the pattern table. Otherwise
the caller's fallback URL + label pass through unchanged.
"""
import re
from urllib.parse import urlparse

from django import template

register = template.Library()


# Ordered — most specific first. Patterns match the path after
# `/employers/`. Query strings are stripped before matching but preserved
# in the returned URL so filter/pagination state comes back with the user.
_BACK_LABELS = [
    (re.compile(r'^jobs/[^/]+/candidates/?$'),   'Back to Applicants'),
    (re.compile(r'^jobs/[^/]+/edit/?$'),         'Back to Job Editor'),
    (re.compile(r'^jobs/[^/]+/?$'),              'Back to Job Post'),
    (re.compile(r'^jobs/create/?$'),             'Back to New Job'),
    (re.compile(r'^jobs/?$'),                    'Back to Jobs'),
    (re.compile(r'^candidates/[^/]+/?$'),        'Back to Candidate'),
    (re.compile(r'^all_candidates/?$'),          'Back to All Candidates'),
    (re.compile(r'^profile/?$'),                 'Back to Company Profile'),
    (re.compile(r'^settings/?$'),                'Back to Settings'),
    (re.compile(r'^dashboard/?$'),               'Back to Dashboard'),
    (re.compile(r'^inbox/?$'),                   'Back to Inbox'),
]


def _label_for(path_after_prefix):
    for pattern, label in _BACK_LABELS:
        if pattern.match(path_after_prefix):
            return label
    return 'Back'


def _resolve_from_referer(request):
    """Returns (url, label) when the Referer is a same-origin `/employers/`
    URL, else (None, None). Ignores off-site referrers and self-referrals."""
    ref = request.META.get('HTTP_REFERER', '')
    if not ref:
        return None, None
    try:
        parsed = urlparse(ref)
    except ValueError:
        return None, None
    if parsed.netloc and parsed.netloc != request.get_host():
        return None, None
    path = parsed.path or ''
    if not path.startswith('/employers/'):
        return None, None
    if path.rstrip('/') == request.path.rstrip('/'):
        return None, None
    # Same reason as in admin_nav: after saving an edit, the referer is the
    # edit page, and we don't want the Back button to bounce the user right
    # back into it. Fall through to the caller's default in that case.
    if path.rstrip('/').endswith('/edit'):
        return None, None
    subpath = path[len('/employers/'):]
    label = _label_for(subpath)
    url = path
    if parsed.query:
        url += '?' + parsed.query
    return url, label


@register.simple_tag(takes_context=True)
def smart_back(context, default_url, default_label):
    """Resolve a smart back-link from the Referer header. Returns a dict
    with `url` and `label` keys; bind with `as back`."""
    request = context.get('request')
    if not request:
        return {'url': default_url, 'label': default_label}
    url, label = _resolve_from_referer(request)
    if url:
        return {'url': url, 'label': label}
    return {'url': default_url, 'label': default_label}
