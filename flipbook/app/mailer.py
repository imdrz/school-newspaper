from __future__ import annotations
import smtplib, ssl
from email.message import EmailMessage
import certifi
from . import config

def send_login_code(to_email: str, code: str, school_name: str) -> None:
    subject = f"Your {school_name} admin login code"
    body = (
        f"Enter this code to sign in as an admin of {school_name}:\n\n"
        f"    {code}\n\n"
        f"It expires in 10 minutes. If you didn't request it, ignore this email."
    )

    if config.EMAIL_BACKEND == "console":
        # Development -> just print it. No real email is sent.
        print("\n===== DEV EMAIL (console backend) =====")
        print("To:     ", to_email)
        print("Subject:", subject)
        print(body)
        print("=======================================\n")
        return

    # Production: send through Gmail over SMTP.
    msg = EmailMessage()
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context(cafile=certifi.where())
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.send_message(msg)
