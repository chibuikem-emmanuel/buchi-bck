# notifications.py
import os
import traceback
import requests
import resend
from django.conf import settings

resend.api_key = getattr(settings, "RESEND_API_KEY", "")

def send_admin_alert(title: str, message: str, priority: str = "default", tags: str = "bell"):
    
    # 1. Send instant push notification to your phone via ntfy.sh
    try:
        topic = getattr(settings, "NTFY_TOPIC", "grove-assets-admin-alerts-xyz987")
        
        # Remove emojis from headers to prevent UnicodeEncodeError, keep plain text
        clean_title = title.encode("ascii", "ignore").decode("ascii").strip() or "Grove Assets Alert"
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": clean_title,
                "Priority": priority,
                "Tags": tags,
            },
            timeout=5,
        )
        print(f"NTFY Response Status: {response.status_code}")
    except Exception as e:
        print("=== NTFY ERROR ===")
        traceback.print_exc()

    # 2. Send email alert to your inbox via Resend
    try:
        admin_email = getattr(settings, "ADMIN_ALERT_EMAIL", "")
        sender_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@groveassetsltd.com")
        
        if admin_email and resend.api_key:
            resend.Emails.send({
                "from": f"Grove Assets <{sender_email}>",
                "to": [admin_email],
                "subject": f"[Grove Assets Alert] {title}",
                "text": message,
            })
    except Exception as e:
        print("=== RESEND ERROR ===")
        traceback.print_exc()