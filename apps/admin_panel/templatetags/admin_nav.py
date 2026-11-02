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


# Pages that belong to ONE specific resource rather than a list. List
# cards (jobseeker_list.html, company_list.html) have a direct "Settings"
# shortcut in their 3-dot menu that jumps straight here, bypassing the
# detail page — so the Referer on these pages is genuinely the list root,
# and a naive smart_back would honestly report "Back to Jobseekers"/
# "Back to Companies". But a settings page is always a child of ONE
# resource, never of the list, so that's the wrong place to send someone
# back to (they lose their spot and have to re-find the person). The
# caller's own fallback on these pages is always "Back to <resource>", so
# we discard a list-root referer match here and let that default win.
_RESOURCE_SUBPAGE = re.compile(r'^(jobseekers|companies)/[^/]+/(settings|edit-resume|verify)/?$')
_LIST_LABELS = {
    'Back to Companies', 'Back to Jobseekers', 'Back to Jobs',
    'Back to User Reports', 'Back to FAQs', 'Back to Announcements',
    'Back to Audit Log', 'Back to Algorithm Settings', 'Back to Site Settings',
    'Back to Sectors', 'Back to Admin Dashboard',
}


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
    # Ignore *edit-shaped* referers so the back-link on a detail page never
    # bounces the admin right back into the form they came from. Covers:
    #   /admin-panel/jobs/<id>/edit               — job edit form
    #   /admin-panel/companies/<id>/settings      — company edit surface
    #   /admin-panel/jobseekers/<id>/settings     — jobseeker admin form
    #   /admin-panel/jobseekers/<id>/edit-resume  — résumé editor
    # After a save + redirect back to the detail page, the referer sits on
    # one of these, and without this guard we'd loop the admin between
    # detail ↔ form endlessly (Kelly's "back to settings ↔ back to
    # company profile" ping-pong). Falls through to the caller's default
    # (usually the list root), which is always safe.
    _stripped = path.rstrip('/')
    if (_stripped.endswith('/edit')
            or _stripped.endswith('/settings')
            or _stripped.endswith('/edit-resume')):
        return None, None
    # Analytics lives at /analytics/ but staff see it in the admin shell —
    # `path.startswith('/admin-panel/')` above already filters that out. If
    # you later want /analytics/ to count as an admin page, extend the
    # allowlist here.
    subpath = path[len('/admin-panel/'):]
    label = _label_for(subpath + (('?' + parsed.query) if parsed.query else ''))
    # A list-root referer on a resource sub-page (settings/edit-resume/
    # verify) means a list card's shortcut was used — the caller's own
    # "Back to <resource>" default is always more useful here than
    # bouncing back to the full list. See _RESOURCE_SUBPAGE above.
    current_path = request.path
    if current_path.startswith('/admin-panel/'):
        current_subpath = current_path[len('/admin-panel/'):]
        if _RESOURCE_SUBPAGE.match(current_subpath) and label in _LIST_LABELS:
            return None, None
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
