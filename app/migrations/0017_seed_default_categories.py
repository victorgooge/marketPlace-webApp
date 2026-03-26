from django.db import migrations

DEFAULT_CATEGORIES = [
    ('Electronics',          'electronics',          'fa-laptop'),
    ('Vehicles',             'vehicles',             'fa-car'),
    ('Clothing & Accessories', 'clothing',           'fa-shirt'),
    ('Home & Garden',        'home-garden',          'fa-house'),
    ('Sports & Outdoors',    'sports-outdoors',      'fa-person-running'),
    ('Toys & Games',         'toys-games',           'fa-gamepad'),
    ('Books & Media',        'books-media',          'fa-book'),
    ('Other',                'other',                'fa-box'),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('app', 'Category')
    for name, slug, icon in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={'name': name, 'icon': icon})


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('app', 'Category')
    slugs = [slug for _, slug, _ in DEFAULT_CATEGORIES]
    Category.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_add_category_model'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
