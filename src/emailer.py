"""Sends a pre-drafted candidate email via Resend.

This module does exactly one thing: transmit a draft that already exists on
disk. It never generates or rewords copy — that happens once, in scorer.py,
and Arjun reviews it on the dashboard before this is ever called. This is
the code-level enforcement of the Cut identified in the Nine Checks: the
system drafts, the founder sends.
"""
import os

import requests

RESEND_URL = "https://api.resend.com/emails"


def send_email(to_address: str, subject: str, body_markdown: str) -> dict:
    api_key = os.environ.get("RESEND_API_KEY")
    from_address = os.environ.get("KARGO_FROM_EMAIL")

    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not set. Create a free account at resend.com, "
            "generate an API key, and export it before calling `send`."
        )
    if not from_address:
        raise RuntimeError(
            "KARGO_FROM_EMAIL is not set — it must be a sender address verified "
            "in your Resend account."
        )

    resp = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [to_address],
            "subject": subject,
            "text": body_markdown,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
