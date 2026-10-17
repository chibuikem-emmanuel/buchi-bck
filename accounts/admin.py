from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('email', 'username', 'balance', 'is_blacklisted', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Financial Info', {'fields': ('balance', 'total_invested', 'total_earned', 'is_blacklisted', 'phone_number')}),
    )

admin.site.register(User, CustomUserAdmin)