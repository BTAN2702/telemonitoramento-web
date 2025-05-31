import os
import logging
from smtplib import SMTP
from email.mime.text import MIMEText
from dotenv import load_dotenv, find_dotenv

# 1) Localiza automaticamente o .env
dotenv_path = find_dotenv()
print(">> .env encontrado em:", dotenv_path)

# 2) Carrega e sobrescreve qualquer variável já presente
load_dotenv(dotenv_path, override=True)

# 3) Mostra as variáveis carregadas
EMAIL_SENDER   = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
print("EMAIL_SENDER after load:", EMAIL_SENDER)
print("EMAIL_PASSWORD after load:", EMAIL_PASSWORD)

# 4) Configura mensagem de teste
TO_ADDRESS = EMAIL_SENDER  # envia para si mesmo
subject    = "Teste de SMTP"
body       = "Este é um e-mail de teste enviado pelo script teste_email.py"

logging.basicConfig(level=logging.DEBUG)

def send_test_email():
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = TO_ADDRESS

    try:
        with SMTP("smtp.gmail.com", 587) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ E-mail de teste enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail de teste: {e}")

if __name__ == "__main__":
    send_test_email()
