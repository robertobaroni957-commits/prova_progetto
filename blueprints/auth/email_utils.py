import smtplib
from email.mime.text import MIMEText

def send_reset_email(to_email, reset_link, simulate=True):
    subject = "🔐 Recupero password ZRL Manager"
    body = f"""Ciao,

Hai richiesto di reimpostare la tua password. Clicca sul link qui sotto per procedere:

{reset_link}

Il link scade tra 1 ora. Se non hai richiesto questa operazione, ignora questa email."""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "noreply@teamzrl.it"
    msg["To"] = to_email

    if simulate:
        print("📧 Simulazione invio email:")
        print("Destinatario:", to_email)
        print("Oggetto:", subject)
        print("Corpo:\n", body)
    else:
        # SMTP reale (da attivare in produzione)
        with smtplib.SMTP("smtp.teamzrl.it", 587) as server:
            server.starttls()
            server.login("noreply@teamzrl.it", "LA_TUA_PASSWORD")
            server.send_message(msg)