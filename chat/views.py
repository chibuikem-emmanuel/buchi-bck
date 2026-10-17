import requests
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import ChatMessage

class SendWhatsAppChatView(generics.CreateAPIView):
    queryset = ChatMessage.objects.all()
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        name = request.data.get('name', 'Visitor')
        email = request.data.get('email', 'Not provided')
        message = request.data.get('message')

        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.is_authenticated:
            ChatMessage.objects.create(user=request.user, name=name, email=email, message=message, is_sent_to_whatsapp=True)
        else:
            ChatMessage.objects.create(name=name, email=email, message=message, is_sent_to_whatsapp=True)

        phone = os.environ.get('ADMIN_WHATSAPP_PHONE', 'YOUR_PHONE_NUMBER')
        apiKey = os.environ.get('CALLMEBOT_API_KEY', 'YOUR_API_KEY')

        formatted_text = (
            f"🚨 *New Crystals Investment Chat*\n\n"
            f"👤 *Name:* {name}\n"
            f"📧 *Email:* {email}\n"
            f"💬 *Message:* {message}"
        )

        callmebot_url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={requests.utils.quote(formatted_text)}&apikey={apiKey}"

        try:
            res = requests.get(callmebot_url)
            if res.status_code == 200:
                return Response({'success': True, 'message': 'Sent to WhatsApp successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to trigger CallMeBot'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)