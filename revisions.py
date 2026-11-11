"""Histórico exibido no aplicativo. Acrescentar cada revisão no início da lista."""

REVISIONS = [
    {
        'version': 'PY04',
        'date': '11/11/2026',
        'changes': [
            'ELU com vento principal e todos os fatores de PP/CP iguais a 1: descartadas hipóteses com outras variáveis acompanhantes, exceto temperatura atmosférica ou de equipamentos. ELS mantém o comportamento anterior.',
            'γ comum de variáveis condicionado a pelo menos 2 grupos cadastrados e ativos. Com um grupo, cada carregamento usa o próprio γ. A contagem independe da presença na combinação.',
            'Variáveis sem grupo contam por ação física; casos vinculados contam juntos. Grupos numéricos contam uma vez, independentemente da compatibilidade.',
            'Retirados os campos Prefixo dos nomes e Observações. Nomes passam a seguir família e sequência, inclusive em projetos antigos. Observações antigas são preservadas nos arquivos e na conferência.',
            'Restrições de presença e de principal de Q dispensam justificativa textual. Fatores manuais continuam exigindo fonte; a escolha de ψ efetivo mantém seu campo de critério.',
            'Incluída esta aba de histórico. Banco normativo e formatos de exportação para Robot, Excel e Word preservados.',
        ],
    },
    {
        'version': 'PY03',
        'date': '27/10/2026',
        'changes': [
            'Incluído o tipo ELU/ELS ou ULS/SLS na segunda coluna das saídas TSV e Excel.',
            'Incluída exportação Word com lista editável das combinações selecionadas, nomes das ações e coeficientes com precisão preservada.',
        ],
    },
    {
        'version': 'PY02',
        'date': '30/09/2026',
        'changes': [
            'Seleção global de famílias, identificação automática da ação física e vínculo avançado entre casos.',
            'Permanentes favoráveis sem justificativa obrigatória, exportação Excel com casos numéricos e melhorias de contraste nas listas.',
            'Limites de geração mantidos como proteções internas, sem campos na interface.',
        ],
    },
]
