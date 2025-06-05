import pytest
from app import (
    hash_senha,
    criptografar_dados,
    descriptografar_dados,
    checar_alerta_custom,
    set_parametro_alerta,
    autenticar,
)


def test_hash_senha():
    senha = 'SenhaForte123!'
    hash1 = hash_senha(senha)
    hash2 = hash_senha(senha)
    assert hash1 == hash2
    assert hash1 != hash_senha('outraSenha')


def test_criptografia():
    dados = {"idade": 30, "diagnostico": "Hipertensão"}
    cript = criptografar_dados(dados)
    assert cript != ''
    dec = descriptografar_dados(cript)
    assert dec == dados


def test_checar_alerta_custom():
    # Simula parâmetros de alerta
    set_parametro_alerta('Temperatura', '35', '38', 'Alerta de temperatura!')
    alerta, sugestao = checar_alerta_custom('Temperatura', '39')
    assert alerta is True
    assert 'Alerta' in sugestao
    alerta, sugestao = checar_alerta_custom('Temperatura', '36')
    assert alerta is False


def test_autenticar_usuario_invalido():
    assert (
        autenticar('naoexiste@email.com', 'senhaqualquer')
        is None
    )
