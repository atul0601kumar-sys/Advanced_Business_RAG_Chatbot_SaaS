from __future__ import annotations

import importlib
import json
import logging
import smtplib
import ssl
import time
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailDeliveryRequest:
    to_addresses: list[str]
    subject: str
    text_body: str
    html_body: str | None = None
    reply_to: list[str] | None = None


class EmailProvider(Protocol):
    name: str

    def send(self, request: EmailDeliveryRequest) -> None:
        ...


class SmtpEmailProvider:
    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, request: EmailDeliveryRequest) -> None:
        if not self.settings.smtp_host:
            raise RuntimeError("SMTP host is not configured.")
        message = EmailMessage()
        message["From"] = self.settings.email_from_address
        message["To"] = ", ".join(request.to_addresses)
        message["Subject"] = request.subject
        if request.reply_to:
            message["Reply-To"] = ", ".join(request.reply_to)
        message.set_content(request.text_body)
        if request.html_body:
            message.add_alternative(request.html_body, subtype="html")
        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.notification_email_timeout_seconds,
        ) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)


class SendGridEmailProvider:
    name = "sendgrid"
    api_url = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, request: EmailDeliveryRequest) -> None:
        if not self.settings.sendgrid_api_key:
            raise RuntimeError("SendGrid API key is not configured.")
        from_email = self.settings.sendgrid_from_email or self.settings.email_from_address
        payload = {
            "personalizations": [{"to": [{"email": address} for address in request.to_addresses]}],
            "from": {"email": from_email},
            "subject": request.subject,
            "content": [{"type": "text/plain", "value": request.text_body}],
        }
        if request.html_body:
            payload["content"].append({"type": "text/html", "value": request.html_body})
        if request.reply_to:
            payload["reply_to_list"] = [{"email": address} for address in request.reply_to]
        encoded = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.api_url,
            data=encoded,
            headers={
                "Authorization": f"Bearer {self.settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            http_request,
            timeout=self.settings.notification_email_timeout_seconds,
        ) as response:
            status_code = getattr(response, "status", 202)
            if status_code >= 400:
                raise RuntimeError(f"SendGrid returned status {status_code}.")


class SesEmailProvider:
    name = "ses"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, request: EmailDeliveryRequest) -> None:
        if not self.settings.aws_region:
            raise RuntimeError("AWS region is not configured for SES.")
        source_address = self.settings.aws_ses_from_email or self.settings.email_from_address
        boto3 = importlib.import_module("boto3")
        botocore_config = importlib.import_module("botocore.config")
        client = boto3.client(
            "ses",
            region_name=self.settings.aws_region,
            config=botocore_config.Config(
                connect_timeout=self.settings.notification_email_timeout_seconds,
                read_timeout=self.settings.notification_email_timeout_seconds,
                retries={"max_attempts": 1},
            ),
        )
        body: dict[str, dict[str, str]] = {"Text": {"Data": request.text_body, "Charset": "UTF-8"}}
        if request.html_body:
            body["Html"] = {"Data": request.html_body, "Charset": "UTF-8"}
        message = {
            "Subject": {"Data": request.subject, "Charset": "UTF-8"},
            "Body": body,
        }
        kwargs = {
            "Source": source_address,
            "Destination": {"ToAddresses": request.to_addresses},
            "Message": message,
        }
        if request.reply_to:
            kwargs["ReplyToAddresses"] = request.reply_to
        client.send_email(**kwargs)


class EmailService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        provider: EmailProvider | None = None,
        sleep_fn=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or self._build_provider()
        self.sleep_fn = sleep_fn or time.sleep

    def send(self, request: EmailDeliveryRequest) -> None:
        if not request.to_addresses:
            logger.info("Email notification skipped because no recipients were provided.")
            return
        attempts = max(1, self.settings.notification_email_max_retries)
        for attempt in range(1, attempts + 1):
            try:
                self.provider.send(request)
                logger.info(
                    "Email notification sent",
                    extra={"provider": self.provider.name, "recipients": request.to_addresses},
                )
                return
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Email notification failed",
                    extra={
                        "provider": getattr(self.provider, "name", "unknown"),
                        "attempt": attempt,
                        "recipients": request.to_addresses,
                    },
                )
                if attempt >= attempts:
                    raise
                self.sleep_fn(self.settings.notification_email_retry_backoff_seconds * attempt)

    def _build_provider(self) -> EmailProvider:
        provider_name = (self.settings.notification_email_provider or "auto").strip().lower()
        if provider_name == "sendgrid":
            return SendGridEmailProvider(self.settings)
        if provider_name == "ses":
            return SesEmailProvider(self.settings)
        if provider_name == "smtp":
            return SmtpEmailProvider(self.settings)
        if self.settings.sendgrid_api_key:
            return SendGridEmailProvider(self.settings)
        if self.settings.aws_region:
            return SesEmailProvider(self.settings)
        return SmtpEmailProvider(self.settings)
