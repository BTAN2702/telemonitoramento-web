import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

# Carrega variáveis do .env
dotenv_path = find_dotenv()
load_dotenv(dotenv_path, override=True)

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

TABELAS_ESPERADAS = {
    "usuarios": ["id", "nome", "email", "senha", "tipo", "status", "primeiro_acesso"],
    "profissionais": ["id", "id_usuario", "especialidade", "registro_profissional"],
    "pacientes": ["id", "id_usuario", "id_profissional_responsavel", "dados_medicos"],
    "sinais_vitais": ["id", "paciente_id", "temperatura", "pressao", "frequencia_cardiaca", "saturacao", "data_registro"],
    "alertas": ["id", "paciente_id", "status", "data_hora"],
    "mensagens": ["id", "id_remetente", "id_destinatario", "texto", "data_envio"],
    "auditoria": ["id", "usuario_id", "acao", "detalhes", "data_hora"],
}

def checar_tabelas_colunas():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
        )
        cursor = conn.cursor()
        print("\n--- Checagem de tabelas e colunas ---\n")
        for tabela, colunas in TABELAS_ESPERADAS.items():
            # Verifica se a tabela existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (tabela,))
            existe = cursor.fetchone()[0]
            if not existe:
                print(f"❌ Tabela NÃO encontrada: {tabela}")
                continue
            # Verifica as colunas
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (tabela,))
            colunas_banco = set([row[0] for row in cursor.fetchall()])
            colunas_esperadas = set(colunas)
            faltando = colunas_esperadas - colunas_banco
            extras = colunas_banco - colunas_esperadas
            if not faltando and not extras:
                print(f"✅ {tabela}: OK")
            else:
                if faltando:
                    print(f"⚠️ {tabela}: Faltando colunas: {faltando}")
                if extras:
                    print(f"⚠️ {tabela}: Colunas extras no banco: {extras}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao checar tabelas: {e}")

if __name__ == "__main__":
    checar_tabelas_colunas() 