Exemplos de Uso
==============

Aqui estão exemplos práticos de como utilizar as principais funções do backend Python.

Cadastrar um novo usuário:
-------------------------

.. code-block:: python

    from app import cadastrar_usuario_novo
    usuario_id = cadastrar_usuario_novo('João', 'joao@email.com', 'Senha@123', 'Paciente')
    print(usuario_id)

Registrar sinais vitais:
-----------------------

.. code-block:: python

    from app import cadastrar_sinais_vitais
    cadastrar_sinais_vitais(1, 36.7, '120/80', 78, 98)

Autenticar usuário:
-------------------

.. code-block:: python

    from app import autenticar
    usuario = autenticar('joao@email.com', 'Senha@123')
    print(usuario) 