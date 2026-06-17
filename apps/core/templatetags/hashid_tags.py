"""Template helpers for hashid-encoded URL slugs.

Load with ``{% load hashid_tags %}`` then use ``{{ obj.id|hashid }}`` in
hardcoded URLs, e.g. ``/admin-panel/jobseekers/{{ js.id|hashid }}/``.
"""

from django import template

from apps.core.hashids import encode

register = template.Library()


@register.filter(name='hashid', is_safe=True)
def hashid_filter(value):
    """Encode an int (or numeric string) to its URL-safe scrambled slug."""
    return encode(value)
