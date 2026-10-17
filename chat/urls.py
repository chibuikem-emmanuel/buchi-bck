from django.urls import path
from .views import SendWhatsAppChatView

urlpatterns = [
    path('send-whatsapp/', SendWhatsAppChatView.as_view(), name='send-whatsapp-chat'),
]