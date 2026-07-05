"""Storage backends for non-image FileFields.

Cloudinary distinguishes between `image` and `raw` resources at the URL level,
so PDFs / docs uploaded through the default (image) storage backend end up with
URLs Cloudinary refuses to serve. This module exposes `raw_media_storage` — a
callable Django can serialize into migrations — that returns the correct
backend based on whether CLOUDINARY_URL is configured.

Usage on a model field:
    from apps.core.storage import raw_media_storage
    file = models.FileField(upload_to='employer_docs/', storage=raw_media_storage)
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def raw_media_storage():
    if getattr(settings, 'CLOUDINARY_URL', ''):
        from cloudinary_storage.storage import RawMediaCloudinaryStorage
        return RawMediaCloudinaryStorage()
    return FileSystemStorage()
