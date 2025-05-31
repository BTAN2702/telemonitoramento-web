# telemonitoramento-web

## Manual do Usuário/Admin

### Visão Geral
Sistema de telemonitoramento para acompanhamento remoto de sinais vitais, com alertas automáticos, mensagens internas, relatórios, auditoria e controle por perfis (admin, profissional, paciente).

### Fluxos Principais
- **Cadastro:** Admin e profissionais podem cadastrar usuários e pacientes.
- **Login:** Autenticação com senha forte e 2FA por e-mail. Troca de senha obrigatória no primeiro acesso.
- **Recuperação de senha:** Clique em "Esqueci minha senha" na tela de login para receber um código por e-mail.
- **Registro de sinais vitais:** Pacientes e profissionais podem registrar múltiplos tipos de sinais.
- **Alertas:** Parâmetros customizáveis pelo admin. Alertas automáticos com sugestão de conduta.
- **Mensagens:** Comunicação interna entre paciente e profissional, com notificação por e-mail.
- **Relatórios:** Visualização e exportação em PDF dos históricos.
- **Auditoria:** Admin pode visualizar logs de todas as ações sensíveis.
- **Consentimento/LGPD:** Paciente deve aceitar termo no primeiro acesso. Admin pode anonimizar/excluir dados.

### Telas e Menus
- **Dashboard:** Cards e gráficos gerenciais (admin).
- **Usuários/Pacientes:** Cadastro, edição, anonimização/exclusão.
- **Sinais Vitais:** Registro, histórico, gráficos.
- **Relatórios:** Filtros, exportação PDF.
- **Mensagens:** Conversa interna, notificações.
- **Auditoria:** Logs de ações.
- **Parâmetros de Alerta:** Configuração dos limites de alerta.
- **Ajuda:** FAQ e contato.

### Instruções de Uso
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure o arquivo `.env` com as variáveis do banco, e-mail e FERNET_KEY.
3. Rode o sistema:
   ```bash
   streamlit run app.py
   ```
4. Acesse no navegador: [http://localhost:8501](http://localhost:8501)
5. Para rodar os testes:
   ```bash
   pytest test_app.py
   ```

### Segurança
- Senha forte obrigatória.
- 2FA por e-mail no login.
- Dados médicos criptografados.
- Consentimento LGPD obrigatório.
- Auditoria de todas as ações sensíveis.

### Documentação Técnica
- **app.py:** Código principal, interface, lógica de negócio, segurança.
- **test_app.py:** Testes unitários com pytest.
- **Requisitos:** Streamlit, psycopg2, pandas, matplotlib, python-dotenv, cryptography, plotly, reportlab.
- **Banco de dados:** PostgreSQL, tabelas: usuarios, profissionais, pacientes, sinais_vitais, alertas, mensagens, auditoria, parametros_alerta.

### Exemplos de Telas
- Login com 2FA
- Dashboard com cards e gráficos
- Cadastro de paciente
- Registro de sinais vitais
- Relatórios em PDF
- Tela de consentimento LGPD
- Mensagens internas
- Auditoria

### Suporte
Dúvidas ou problemas? Entre em contato: suporte@ceub.edu.br

## Instalação

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure o arquivo `.env` na raiz do projeto com as variáveis:
   ```env
   DB_HOST=localhost
   DB_NAME=telemonitoramento
   DB_USER=postgres
   DB_PASSWORD=sua_senha
   DB_PORT=5432
   EMAIL_SENDER=seu_email@gmail.com
   EMAIL_PASSWORD=sua_senha_email
   ```

3. Crie o banco de dados e as tabelas (veja abaixo).

4. Execute o sistema:
   ```bash
   streamlit run app.py
   ```

## Script SQL para criar as tabelas

```sql
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha VARCHAR(256) NOT NULL,
    perfil VARCHAR(30) NOT NULL,
    especialidade VARCHAR(100),
    registro_profissional VARCHAR(50)
);

CREATE TABLE pacientes (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    idade INTEGER NOT NULL,
    diagnostico VARCHAR(200),
    profissional_responsavel_id INTEGER NOT NULL REFERENCES usuarios(id)
);

CREATE TABLE sinais_vitais (
    id SERIAL PRIMARY KEY,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
    temperatura REAL NOT NULL,
    pressao VARCHAR(10) NOT NULL,
    frequencia_cardiaca INTEGER NOT NULL,
    saturacao INTEGER NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Observações
- O usuário padrão do banco é `postgres`. Se mudar, ajuste o `.env`.
- O envio de e-mails requer uma conta Gmail e senha de app.