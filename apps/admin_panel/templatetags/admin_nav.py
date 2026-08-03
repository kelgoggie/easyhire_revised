"""Template tags for the admin panel — currently just the smart-back helper.

Usage in an admin template:

    {% load admin_nav %}
    {% smart_back "/admin-panel/jobseekers/" "Back to Jobseekers" as back %}
    <a href="{{ back.url }}">... {{ back.label }}</a>

`{% smart_back %}` looks at the Referer header. If the previous page was
somewhere else inside `/admin-panel/`, it uses that URL and picks a label
by matching the path against a small pattern table. Otherwise the caller's
fallback URL + label are returned unchanged, which preserves the current
behaviour of every existing admin page.
"""
import re
from urllib.parse import urlparse

from django import template

register = template.Library()


# Ordered list of (compiled path pattern, label). First match wins, so put
# more specific patterns before broader ones. Patterns match the URL path
# after `/admin-panel/`.
_BACK_LABELS = [
    # ── Specific sub-pages (must come before their list roots) ──
    (re.compile(r'^companies/[^/]+/jobs/[^/]+/?$'),         'Back to Job Post'),
    (re.compile(r'^companies/[^/]+/settings/?$'),           'Back to Company Settings'),
    (re.compile(r'^companies/[^/]+/verify/?$'),             'Back to Company Verification'),
    (re.compile(r'^companies/[^/]+/?$'),                    'Back to Company Profile'),
    (re.compile(r'^jobseekers/[^/]+/settings/?$'),          'Back to Jobseeker Settings'),
    (re.compile(r'^jobseekers/[^/]+/edit-resume/?$'),       'Back to Résumé Editor'),
    (re.compile(r'^jobseekers/[^/]+/applications/[^/]+/?$'),'Back to Application'),
    (re.compile(r'^jobseekers/[^/]+/?$'),                   'Back to Jobseeker Profile'),
    (re.compile(r'^faqs/[^/]+/?$'),                         'Back to FAQ Editor'),

    # ── List / index pages ──
    (re.compile(r'^companies/?(\?.*)?$'),                   'Back to Companies'),
    (re.compile(r'^jobseekers/?(\?.*)?$'),                  'Back to Jobseekers'),
    (re.compile(r'^jobs/?(\?.*)?$'),                        'Back to Jobs'),
    (re.compile(r'^reports/?(\?.*)?$'),                     'Back to User Reports'),
    (re.compile(r'^faqs/?(\?.*)?$'),                        'Back to FAQs'),
    (re.compile(r'^announcements/?(\?.*)?$'),               'Back to Announcements'),
    (re.compile(r'^audit-log/?(\?.*)?$'),                   'Back to Audit Log'),
    (re.compile(r'^algorithm-settings/?(\?.*)?$'),          'Back to Algorithm Settings'),
    (re.compile(r'^site-settings/?(\?.*)?$'),               'Back to Site Settings'),
    (re.compile(r'^sectors/?(\?.*)?$'),                     'Back to Sectors'),

    # ── Admin root ──
    (re.compile(r'^/?(\?.*)?$'),                            'Back to Admin Dashboard'),
]


def _label_for(path_after_admin):
    for pattern, label in _BACK_LABELS:
        if pattern.match(path_after_admin):
            return label
    return 'Back'


def _resolve_from_referer(request):
    """Returns (url, label) when the Referer is a same-origin admin URL,
    else (None, None). Same-origin check compares the host header so a link
    from an off-site page (Google, email link) doesn't leak into the label.
    """
    ref = request.META.get('HTTP_REFERER', '')
    if not ref:
        return None, None
    try:
        parsed = urlparse(ref)
    except ValueError:
        return None, None
    request_host = request.get_host()
    if parsed.netloc and parsed.netloc != request_host:
        return None, None
    path = parsed.path or ''
    if not path.startswith('/admin-panel/'):
        return None, None
    # Ignore self-referrals so a POST-then-render pattern doesn't yield
    # a "Back to <same page>" link.
    if path.rstrip('/') == request.path.rstrip('/'):
        return None, None
    # Analytics lives at /analytics/ but staff see it in the admin shell —
    # `path.startswith('/admin-panel/')` above already filters that out. If
    # you later want /analytics/ to count as an admin page, extend the
    # allowlist here.
    subpath = path[len('/admin-panel/'):]
    label = _label_for(subpath + (('?' + parsed.query) if parsed.query else ''))
    # Reattach the query string so filter/pagination state is preserved
    # ('/admin-panel/jobseekers/?page=3' → back link lands on page 3).
    url = path
    if parsed.query:
        url += '?' + parsed.query
    return url, label


@register.simple_tag(takes_context=True)
def smart_back(context, default_url, default_label):
    """Resolve a smart back-link from the Referer header. Returns a dict
    with `url` and `label` keys; callers use `as back` to bind it.
    """
    request = context.get('request')
    if not request:
        return {'url': default_url, 'label': default_label}
    url, label = _resolve_from_referer(request)
    if url:
        return {'url': url, 'label': label}
    return {'url': default_url, 'label': default_label}
