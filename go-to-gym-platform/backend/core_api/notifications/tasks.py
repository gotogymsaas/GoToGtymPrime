from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from firebase_admin import messaging
from celery import shared_task


@shared_task
def send_push_notification(token, title, body):
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
    )
    messaging.send(message)


@shared_task
def send_email_notification(email, subject, body, template="generic_notification.html", context=None):
    context = context or {"body": body, "title": subject}
    html_message = render_to_string(f"notifications/emails/{template}", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], html_message=html_message)
