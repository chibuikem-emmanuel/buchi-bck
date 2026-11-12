# notifications.py
import threading
import requests
import resend
from django.conf import settings

resend.api_key = getattr(settings, "RESEND_API_KEY", "")

def _dispatch_alert(title: str, message: str, priority: str = "default", tags: str = "bell"):
    # 1. Send instant push notification to your phone via ntfy.sh
    try:
        topic = getattr(settings, "NTFY_TOPIC", "grove-assets-admin-alerts")
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,  # "high" or "urgent" makes your phone buzz/ring immediately
                "Tags": tags,
            },
            timeout=5,
        )
    except Exception as e:
        print(f"Push alert failed: {e}")

    # 2. Send email alert to your inbox via Resend using your custom domain
    try:
        admin_email = getattr(settings, "ADMIN_ALERT_EMAIL", "")
        # Use your professional domain address here:
        sender_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@groveassetsltd.com")
        
        if admin_email and resend.api_key:
            resend.Emails.send({
                "from": f"Grove Assets <{sender_email}>",
                "to": [admin_email],
                "subject": f"[Grove Assets Alert] {title}",
                "text": message,
            })
    except Exception as e:
        print(f"Resend email alert failed: {e}")

def send_admin_alert(title: str, message: str, priority: str = "default", tags: str = "bell"):
    """Runs alerts in a background thread so user API requests never lag."""
    thread = threading.Thread(
        target=_dispatch_alert,
        args=(title, message, priority, tags),
        daemon=True,
    )
    thread.start()