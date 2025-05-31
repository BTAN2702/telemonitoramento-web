Fluxograma do Registro de Sinais Vitais
======================================

.. mermaid::

   graph TD
      A[Usuário logado] --> B{Já registrou hoje?}
      B -- Sim --> C[Fim]
      B -- Não --> D[Preencher sinais vitais]
      D --> E[Validar dados]
      E -- Inválido --> F[Exibir alerta]
      E -- Válido --> G[Salvar no banco]
      G --> H[Notificar profissional]
      H --> I[Fim] 