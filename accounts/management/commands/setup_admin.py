import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Ensures a default superuser exists and updates password if needed'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@crystalsinvestments.org')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'supersecurepass123')
        username = 'admin'

        user = User.objects.filter(email=email).first()
        if not user:
            # Create a brand new superuser with correct hashing
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser {email} created successfully!'))
        else:
            # Force-update password to guarantee login works
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Superuser {email} credentials verified and updated!'))