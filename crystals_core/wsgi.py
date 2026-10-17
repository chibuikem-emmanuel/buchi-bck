"""
WSGI config for crystals_core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crystals_core.settings')

application = get_wsgi_application()


# Auto-create admin user on startup if it doesn't exist
try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(email='admin@crystalsinvestments.org').exists():
        User.objects.create_superuser('admin@crystalsinvestments.org', 'AdminSecurePassword123!', username='AdminUser')
        print("Default superuser created automatically.")
except Exception as e:
    print("Superuser auto-creation skipped or failed:", e)
