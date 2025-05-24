import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText

# Carrega as variáveis do arquivo .env
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

msg = MIMEText("Teste de envio SMTP")
msg['Subject'] = "Teste"
msg['From'] = EMAIL_SENDER
msg['To'] = EMAIL_SENDER  # Pode trocar para outro e-mail de teste, se quiser

try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
    print("Email enviado com sucesso!")
except Exception as e:
    print(f"Erro ao enviar email: {e}")
