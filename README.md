# Combinações ELU / ELS para Robot

Aplicativo Python + Streamlit, em português, para cadastrar ações e gerar combinações com saída tabulada para o Autodesk Robot Structural Analysis. Versão inicial PY01, preparada para GitHub e Streamlit Community Cloud.

## Publicar pelo GitHub + Streamlit

1. Extraia o ZIP. Entre na pasta `gerador-combinacoes`.
2. Crie um repositório no GitHub e envie **o conteúdo dessa pasta**. `app.py`, `engine.py`, `project_io.py`, `catalog.json` e `requirements.txt` devem estar na raiz do repositório. Inclua também `tests`, `examples` e `.streamlit`. Não envie somente o ZIP.
3. Acesse [Streamlit Community Cloud](https://share.streamlit.io/), conecte sua conta GitHub e escolha **Create app**.
4. Selecione o repositório e sua branch, normalmente `main`. No campo de arquivo principal, informe **`app.py`**. Nas configurações avançadas, selecione Python **3.12**, usado na verificação desta versão.
5. Clique em **Deploy**. O Streamlit instala as dependências de `requirements.txt` e fornece o endereço do aplicativo.
6. Abra o aplicativo, use **Abrir / salvar projeto → Carregar exemplo didático**, depois **02 · Gerar e copiar → Gerar combinações**. Devem aparecer **54 combinações**.

O pacote está pronto para publicação, mas não contém um repositório criado nem um endereço já publicado. Escolha a visibilidade e o acesso adequados ao uso da sua equipe. Não há autenticação implementada dentro do aplicativo; use os controles da hospedagem se precisar restringir o acesso.

Documentação oficial: [publicação](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [dependências](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

## Executar no computador

Requer Python 3.12. Na pasta do projeto:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Abra o endereço exibido no terminal, normalmente `http://localhost:8501`.

## Usar no projeto estrutural

- No menu lateral, selecione norma, famílias e ponderação de G/Q.
- Cada cadastro corresponde a um **caso numérico existente no Robot**. Nomeie-o livremente.
- Escolha o tipo e a categoria ψ. Marque explicitamente as famílias aplicáveis a cada ação.
- **Origem:** identifica uma ação física. Partes da mesma ação usam a mesma origem e variam juntas. Controles ou fatores conflitantes dentro da origem bloqueiam a geração. A natureza também faz parte da identificação interna: G e Q não são unidas por um texto de origem igual.
- **Grupo:** relaciona ações diferentes. No grupo incompatível, entra no máximo uma origem por combinação; no grupo compatível, podem coexistir. Compatibilidade não obriga simultaneidade.
- Exemplo dos ventos: quatro casos, quatro origens, um mesmo grupo incompatível.
- G pode variar favorável/desfavorável ou ter uma das ponderações restringida. Q pode variar presença/ausência ou ser obrigatória, e pode ser impedida de atuar como principal em ELU normal/ELS. Restrições relevantes exigem justificativa.
- Clique em **Gerar combinações**. O aplicativo impede a exportação de resultados antigos quando as entradas salvas mudam. Alterações ainda não salvas no formulário de ação não mudam o projeto.
- Na saída, escolha famílias e separador decimal. Use o ícone de copiar do bloco tabulado ou baixe o TSV.

### Colagem no Robot

O conteúdo não tem cabeçalho e segue:

`Nome → Caso → Coeficiente → Caso → Coeficiente → …`

Cole a partir da coluna **Nome**. Não é exportada a coluna de numeração automática “Combinações”. A estrutura segue o formato de ida e volta Excel/Robot validado na conversa; esta implementação Python ainda não foi testada dentro de uma instalação do Robot. Na primeira colagem, confira em uma cópia do modelo os casos, os coeficientes, a quantidade de linhas e a classificação nativa ELU/ELS. O prefixo do nome **não** configura o tipo de combinação do Robot.

O TSV também pode ser aberto no Excel, usando tabulação como delimitador. A conferência CSV é outro arquivo: não é a tabela a colar no Robot.

### Guardar o trabalho

Baixe o **projeto JSON** para salvar entradas, critérios, justificativas e versão do banco. Para continuar, abra esse arquivo no menu lateral. A sessão do navegador não é um arquivo persistente. Os resultados são recalculados ao reabrir. Cada sessão mantém suas próprias entradas; não há banco compartilhado de projetos.

Em uma hospedagem Streamlit, as entradas são processadas no servidor. O código não usa telemetria própria nem serviços externos para os cálculos e não armazena automaticamente os projetos em disco. Arquivos baixados ficam sob controle do usuário.

## Banco normativo e escopo

Banco com 55 linhas de γ e 26 linhas de ψ, separado por norma:

- NBR 8800:2024, considerando a errata de 2025; Tabelas 1 e 2 e critérios de combinação.
- NBR 14762:2010; Tabelas 1 e 2 e critérios de combinação.
- NBR 8681:2025; tabelas e critérios identificados em cada registro.

As referências de tabela/página e observações estão em `catalog.json` e são exibidas na interface. O banco foi migrado dos documentos usados na versão Excel; não incorpora automaticamente futuras revisões de normas. Os PDFs integrais não são redistribuídos neste pacote.

| Família | Composição aplicada |
|---|---|
| ELU normal | G ponderadas + Q principal ponderada + acompanhantes ponderadas com ψ0 |
| ELU especial / construção | G ponderadas + Q especial/de construção principal + acompanhantes com ψ efetivo |
| ELU excepcional | G ponderadas + ação excepcional + Q acompanhantes com ψ efetivo |
| ELS rara | G + Q principal + acompanhantes com ψ1 |
| ELS frequente | G + principal com ψ1 + acompanhantes com ψ2 |
| ELS quase permanente | G + Q com ψ2, sem iteração de principal |

A seleção entre ψ0 e ψ2 nas situações especiais, de construção e excepcionais é explícita e exige justificativa compatível com a duração/condição normativa. Para ELU especial/construção, indique o papel das variáveis naquela família. Para ELU excepcional, cadastre a ação excepcional própria.

As ponderações de G são compartilhadas por origem física. Quando G diretas são ponderadas em conjunto, compartilham um único controle. O agrupamento de γQ não une as ações físicas nem impede a iteração de principais. Para NBR 14762, a faixa de uso/ocupação é solicitada quando necessária. Para NBR 14762 e NBR 8681, o agrupamento de Q exige G diretas agrupadas. O tratamento da temperatura atmosférica é escolhido explicitamente.

Tipos/categorias ausentes na norma escolhida não recebem fatores de outra norma. A categoria **Personalizada** permite fatores informados pelo calculista, com fonte, justificativa e vínculo à norma selecionada; a conferência os identifica como **MANUAL**. Ações personalizadas diretas G e Q exigem ponderação separada da respectiva natureza.

Não há verificação de barras, dimensionamento ou memória de cálculo. O gerador não implementa automaticamente sismo, incêndio, fadiga, não linearidade, imperfeições ou regras particulares externas ao banco. Fatores favoráveis/desfavoráveis não são inferidos de esforços do modelo.

### Crescimento da quantidade de combinações

O motor considera principais, presenças/ausências permitidas, ponderações G e incompatibilidades. Elimina duplicatas exatas **dentro da mesma família**, mantendo a indicação das principais equivalentes. Termos de coeficiente zero não são exportados. Casos sem variável principal são gerados quando permitidos em ELU normal/ELS rara/frequente. Presenças obrigatórias e incompatibilidades podem tornar uma família inviável: nesse caso a geração é bloqueada, sem omissão silenciosa da família.

Limites da interface: 200 ações, até 50.000 combinações e 5.000.000 de visitas internas. Os padrões são 20.000 combinações e 500.000 visitas. Limite excedido interrompe a geração sem liberar uma saída parcial. A faixa de entrada de γ é de 0 a 100, e a de ψ de 0 a 1; esses limites são validações do aplicativo, não recomendações normativas.

## Verificação e manutenção

```bash
python -m unittest discover -s tests -v
```

Foram executados 37 testes: 32 do motor/arquivos e 5 da interface via Streamlit AppTest. O exemplo tem 28 ELU normais, 14 ELS raras, 10 ELS frequentes e 2 ELS quase permanentes. Seus vetores foram comparados com a referência exportada da versão anterior, além de testes específicos de incompatibilidade, mesma origem, restrições, fatores por norma, situações especiais/excepcionais e limites.

A comparação com a versão anterior é uma verificação de regressão, não uma certificação normativa independente. O AppTest verifica eventos e estado da interface; não executa a área de transferência do navegador nem a colagem no Robot.

Estrutura:

- `app.py`: interface.
- `engine.py`: motor independente, com aritmética Decimal.
- `catalog.json`: banco com fatores, fontes e observações.
- `project_io.py`: importação/exportação de projetos, TSV e CSV.
- `tests/`: testes e referência do exemplo.
- `examples/`: projeto didático e saída correspondente.
- `.streamlit/config.toml`: tema e limite de upload.
- `requirements.txt`: versões de dependências usadas na verificação.

Projetos carregam a identificação do banco e recusam versões diferentes. Mudanças de fatores devem ser revisadas explicitamente; não edite o identificador de um projeto antigo apenas para contornar esse controle.
