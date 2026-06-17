"""Reversible URL slug encoding for integer PKs.

Used to scramble model IDs in URLs so they don't expose raw sequential
integers (e.g. ``/admin-panel/jobseekers/2/`` becomes
``/admin-panel/jobseekers/qK4w/``). Encoding is reversible — the path
converter decodes the slug back to an int before the view sees it, so
view signatures and ORM lookups don't change.

Not for use as a security mechanism — anyone can install the same
library and try common salts. It's obfuscation, not encryption.
"""

from django.conf import settings
from hashids import Hashids


_hasher = Hashids(
    salt=getattr(settings, 'HASHIDS_SALT', settings.SECRET_KEY),
    min_length=6,
    alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ23456789',
)


def encode(value):
    """Encode an int (or numeric string) to its slug. Returns '' on bad input."""
    try:
        return _hasher.encode(int(value))
    except (TypeError, ValueError):
        return ''


def decode(slug):
    """Decode a slug back to the original int, or None if the slug is invalid."""
    if not slug:
        return None
    result = _hasher.decode(str(slug))
    return result[0] if result else None


class HashidConverter:
    """Django URL converter that transparently encodes/decodes hashids.

    Register once in ``config/urls.py`` and then use ``<hashid:pk>`` in
    URL patterns exactly like ``<int:pk>`` — the view still receives an
    int, and ``{% url %}`` / ``reverse()`` calls auto-encode when given
    an int.
    """
    regex = r'[A-Za-z2-9]{6,32}'

    def to_python(self, value):
        decoded = decode(value)
        if decoded is None:
            # Raising ValueError makes Django treat the URL as a 404 rather
            # than crashing with a 500.
            raise ValueError(f'Invalid hashid slug: {value!r}')
        return decoded

    def to_url(self, value):
        return encode(value)
