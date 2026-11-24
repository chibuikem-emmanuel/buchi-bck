import os
import traceback
import requests
import resend
from django.conf import settings


def _get_resend_api_key() -> str:
    key = getattr(settings, "RESEND_API_KEY", "") or os.getenv("RESEND_API_KEY", "")
    resend.api_key = key
    return key


def send_admin_alert(title: str, message: str, priority: str = "default", tags: str = "bell"):
    # 1. Send instant push notification via ntfy.sh
    try:
        topic = getattr(settings, "NTFY_TOPIC", "grove-assets-admin-alerts-xyz987")
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
    except Exception:
        print("=== NTFY ERROR ===")
        traceback.print_exc()

    # 2. Send email alert to admin via Resend
    try:
        api_key = _get_resend_api_key()
        admin_email = getattr(settings, "ADMIN_ALERT_EMAIL", "")
        sender_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@groveassetsltd.com")

        if admin_email and api_key:
            resend.Emails.send({
                "from": f"Grove Assets <{sender_email}>",
                "to": [admin_email],
                "subject": f"[Grove Assets Alert] {title}",
                "text": message,
            })
        else:
            print("=== RESEND WARNING: Missing ADMIN_ALERT_EMAIL or RESEND_API_KEY ===")
    except Exception:
        print("=== RESEND ERROR ===")
        traceback.print_exc()


def send_user_email(to_email: str, subject: str, message: str) -> bool:
    if not to_email:
        return False

    try:
        api_key = _get_resend_api_key()
        sender_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@groveassetsltd.com")

        if not api_key:
            print("=== USER RESEND WARNING: Missing RESEND_API_KEY ===")
            return False

        response = resend.Emails.send({
            "from": f"Grove Assets <{sender_email}>",
            "to": [to_email],
            "subject": subject,
            "text": message,
        })
        print(f"User email sent to {to_email}: {response}")
        return True
    except Exception:
        print(f"=== USER RESEND ERROR ({to_email}) ===")
        traceback.print_exc()
        return False