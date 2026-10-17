from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/investments/', include('investments.urls')),
    path('api/', include('investments.urls')),
    path('api/chat/', include('chat.urls')),
]