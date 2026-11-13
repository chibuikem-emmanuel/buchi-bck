# notifications.py
import os
import traceback
import requests
import resend
from django.conf import settings

resend.api_key = getattr(settings, "RESEND_API_KEY", "")

def send_admin_alert(title: str, message: str, priority: str = "default", tags: str = "bell"):
    """Runs alerts synchronously so we can see any errors directly in Render logs."""
    
    # 1. Send instant push notification to your phone via ntfy.sh
    try:
        topic = getattr(settings, "NTFY_TOPIC", "grove-assets-admin-alerts-xyz987")
        print(f"Attempting to send ntfy alert to topic: {topic}")
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags,
            },
            timeout=5,
        )
        print(f"NTFY Response Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print("=== NTFY ERROR ===")
        traceback.print_exc()

    # 2. Send email alert to your inbox via Resend
    try:
        admin_email = getattr(settings, "ADMIN_ALERT_EMAIL", "")
        sender_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@groveassetsltd.com")
        
        print(f"Attempting to send Resend email to: {admin_email} from {sender_email}")
        print(f"Resend API Key loaded: {bool(resend.api_key)}")
        
        if admin_email and resend.api_key:
            res_result = resend.Emails.send({
                "from": f"Grove Assets <{sender_email}>",
                "to": [admin_email],
                "subject": f"[Grove Assets Alert] {title}",
                "text": message,
            })
            print(f"Resend Success Result: {res_result}")
    except Exception as e:
        print("=== RESEND ERROR ===")
        traceback.print_exc()