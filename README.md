# Taranis Black — Analisador Financeiro

Aplicação web acadêmica desenvolvida para o Challenge ONE G11 — AI for
Business. O projeto servirá como ponto de partida para explorar indicadores
financeiros e operacionais com Python.

Atualmente, a aplicação permite importar uma planilha Excel `.xlsx`, escolher
uma de suas abas, visualizar os dados e analisar comparações de orçamento e
realizado nas estruturas reconhecidas da DRE e das linhas de produto. O
dashboard também apresenta gráficos interativos e alertas baseados em regras.

## Requisitos

- Python 3 instalado
- `pip`, o instalador de pacotes do Python

## Preparar o ambiente

Abra um terminal nesta pasta e crie um ambiente virtual:

```powershell
python -m venv .venv
```

Ative-o no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação por política de execução, use o Prompt de
Comando e execute:

```cmd
.venv\Scripts\activate.bat
```

Com o ambiente virtual ativado, instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

## Executar a aplicação

Ainda com o ambiente virtual ativado, inicie o Streamlit:

```powershell
python -m streamlit run app.py
```

O Streamlit abrirá a página no navegador. Para encerrar, pressione `Ctrl+C` no
terminal.

## Aparência

A aplicação usa um tema azul-claro configurado em `.streamlit/config.toml`,
com fundo azul suave e texto escuro para facilitar a leitura.

## Importar uma planilha

Na seção **Importação de Dados Financeiros**, envie um arquivo `.xlsx`. A
aplicação identifica as abas disponíveis para seleção e exibe a aba escolhida,
seu número de registros, seu número de colunas e os dados lidos. Esta etapa não
altera nem salva a planilha.

## Análise orçado × realizado

Para abas reconhecidas como DRE ou linhas de produto, a seção **Análise
Financeira — Orçado × Realizado** apresenta os valores orçados e realizados,
os desvios absolutos e percentuais e uma classificação financeira. É possível
filtrar por período, categoria e indicador.

O desvio absoluto é `Realizado − Orçado`; o percentual é
`(Desvio absoluto / Orçado) × 100`. Quando o orçamento é zero, o percentual
fica indisponível. Valores ausentes permanecem ausentes. Despesas contabilizadas
com sinal negativo são classificadas levando em conta esse sinal. Como o
percentual usa o orçamento com seu sinal original, um aumento de despesa pode
aparecer como percentual positivo, mas receber classificação desfavorável.

A tabela mantém as linhas reportadas sem agregá-las. Indicadores-resumo usam
somente linhas totais explícitas da planilha, sem somá-las novamente aos seus
componentes. A aba de gargalos operacionais contém metas em texto e a aba de
dashboard contém dados derivados e projeções; elas não entram nesta comparação.

## Dashboard, filtros e alertas

Os filtros de período, categoria e indicador ficam na barra lateral e afetam os
indicadores, gráficos, alertas e tabela. Os gráficos comparam valores sem
agregação; a evolução usa somente os trimestres disponíveis, sem tratar o total
anual como um trimestre. O gráfico de maiores desvios considera apenas linhas
classificadas como desfavoráveis. O resumo de despesas soma apenas as linhas
classificadas como despesas e incluídas nos filtros; EBITDA e subtotais não são
somados às despesas.

O limite de alerta começa em 10% e pode ser ajustado. Despesas acima do
orçamento, receitas abaixo do orçamento e EBITDA abaixo do orçamento geram
alertas quando o desvio percentual é calculável e atinge o limite. Um orçamento
zero não produz alerta percentual. Desvios de pelo menos o dobro do limite
configurado são apresentados como alerta de gravidade alta; os demais alertas
que atingem o limite são apresentados como atenção. Recomendações, quando
aplicáveis, são sugestões para avaliação humana, não decisões automáticas nem
detecção por aprendizado de máquina.

## Relatório executivo

A seção **Relatório Executivo** gera uma prévia e permite baixar um HTML com os
filtros ativos, período, data de geração, valores comparativos, alertas e
recomendações justificadas pelos dados. O HTML pode ser impresso ou salvo como
PDF pelo navegador; a aplicação não gera PDF diretamente. Textos da planilha
são escapados antes de serem incluídos no documento.

Execute os testes automatizados com:

```powershell
python -m pytest
```

## Preparação para publicar no GitHub

O `.gitignore` exclui ambientes virtuais, credenciais e planilhas Excel para
evitar publicar dados importados acidentalmente. Antes de enviar o projeto,
revise os arquivos que serão incluídos e confirme que não há dados pessoais,
credenciais ou relatórios locais. O repositório Git deve ser inicializado e
associado ao GitHub pela pessoa responsável pelo projeto.

## Organização dos arquivos

- `app.py`: apresenta a interface Streamlit para importar e visualizar uma
  planilha.
- `requirements.txt`: lista as bibliotecas que serão usadas no projeto.
- `.gitignore`: evita incluir ambientes virtuais, arquivos temporários e
  credenciais no controle de versão.
- `data/`: reservado para arquivos de dados adicionados em etapas futuras.
- `src/__init__.py`: identifica `src` como um pacote Python.
- `src/analise_financeira.py`: lê abas e implementa cálculos, classificação e
  preparação de comparativos, indicadores-resumo, alertas e recomendações.
- `src/relatorio_financeiro.py`: gera o relatório executivo HTML a partir dos
  dados filtrados pelo dashboard.
- `src/formatacao.py`: centraliza a formatação de valores monetários e percentuais.
- `src/visualizacoes.py`: cria os gráficos interativos em Plotly.
- `tests/`: verifica cálculos, alertas, filtros de dados, gráficos e relatório.
