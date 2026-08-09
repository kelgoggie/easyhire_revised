"""Rename user-facing 'liked' language to 'bookmarked' in the seeded FAQ
row. The 0008_seed_faqs seed inserted the row with 'Liked'; the source in
seed_faqs.py has since been updated to 'Bookmarked' but existing DB rows
weren't touched (the seed command is idempotent — it never rewrites).
"""
from django.db import migrations


OLD_Q = "How do I see jobs I've liked or hidden?"
NEW_Q = "How do I see jobs I've bookmarked or hidden?"
OLD_A = (
    "On the <strong>Jobs For You</strong> page, switch to the <strong>Liked</strong> "
    "or <strong>Hidden</strong> tab at the top. Hidden jobs won't appear in your main "
    "recommendations, but you can unhide them at any time by clicking the slashed-eye "
    "icon on the card."
)
NEW_A = (
    "On the <strong>Jobs For You</strong> page, switch to the <strong>Bookmarked</strong> "
    "or <strong>Hidden</strong> tab at the top. Hidden jobs won't appear in your main "
    "recommendations, but you can unhide them at any time by clicking the slashed-eye "
    "icon on the card."
)


def _rename(apps, schema_editor):
    FAQ = apps.get_model('admin_panel', 'FAQ')
    FAQ.objects.filter(question=OLD_Q).update(question=NEW_Q, answer=NEW_A)


def _revert(apps, schema_editor):
    FAQ = apps.get_model('admin_panel', 'FAQ')
    FAQ.objects.filter(question=NEW_Q).update(question=OLD_Q, answer=OLD_A)


class Migration(migrations.Migration):
    dependencies = [
        ('admin_panel', '0012_alter_importbatch_file'),
    ]

    operations = [
        migrations.RunPython(_rename, _revert),
    ]
