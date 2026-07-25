import json
import os

from pywebpush import WebPushException, webpush

VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")


def send_push(subscription, title: str, body: str, url: str = "/") -> str:
    """Envía una notificación push. Devuelve 'ok', 'expired' o 'error'."""
    private_key = os.environ["VAPID_PRIVATE_KEY"]
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=private_key,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return "ok"
    except WebPushException as ex:
        status_code = getattr(ex.response, "status_code", None)
        if status_code in (404, 410):
            return "expired"
        print(f"Push falló para {subscription.endpoint}: {ex}")
        return "error"
