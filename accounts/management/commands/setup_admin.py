from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a default superuser if none exists'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@crystalsinvestments.org')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'securepassword123')
        
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(email=email, username='admin', password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser {email} created successfully!'))
        else:
            self.stdout.write(self.style.WARNING('Superuser already exists.'))