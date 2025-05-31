.. Telemonitoramento CEUB documentation master file, created by
   sphinx-quickstart on 2024.

Bem-vindo à documentação do Telemonitoramento CEUB!
===================================================

.. toctree::
   :maxdepth: 2
   :caption: Conteúdo

   sobre
   tutorial
   exemplos
   fluxograma
   faq
   api

Sumário
-------

- Sistema robusto para monitoramento remoto de sinais vitais
- Multiusuário, seguro, com autenticação 2FA e criptografia
- Alertas automáticos, relatórios, mensagens e auditoria

Veja os tópicos ao lado para exemplos, tutoriais, fluxogramas e referência completa da API.

Introdução
----------
Este sistema realiza o telemonitoramento de pacientes, com backend em Python (Streamlit, PostgreSQL) e frontend web. Inclui cadastro, autenticação, registro de sinais vitais, alertas, mensagens, auditoria, relatórios, LGPD, segurança e dashboard.

Geração da documentação
-----------------------
Para gerar a documentação HTML localmente:

.. code-block:: bash

   cd docs
   make html

Acesse o resultado em ``docs/_build/html/index.html``.

Documentação automática do backend
----------------------------------
Abaixo, a referência automática dos módulos Python principais:

.. automodule:: app
   :members:
   :undoc-members:
   :show-inheritance: 