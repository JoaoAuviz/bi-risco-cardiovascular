# Data Mart de Exames Cardíacos — ETL e carga (esquema estrela)

Trabalho final (CONIC-SEMESP) — FATEC Bauru, Análise e Desenvolvimento de Sistemas.

Pipeline em Python que lê o `Medicaldataset.csv` (Kaggle, 1.319 registros), limpa e
transforma os dados e carrega um **esquema estrela**: `fato_exames_cardiacos` +
`dim_paciente` + `dim_clinica`. Inclui validação da carga e as duas necessidades do
gestor (uma fato + uma dimensão: `fato_exames_cardiacos` e `dim_paciente`).

## Estrutura

| Caminho | Função |
|---|---|
| `sql/01_ddl_datamart.sql` | DDL do Data Mart (Anexo A da Entrega Parcial 1) |
| `01_etl_carga.py` | Extração, limpeza, transformação e carga |
| `02_validacao.py` | Contagens, integridade, testes de restrição e consultas do gestor |
| `03_gerar_relatorio.py` | Gera o relatório PDF (ABNT) a partir dos resultados reais |
| `tools/gerar_base_teste.py` | Gera base sintética **só para testar** o pipeline |
| `dados/` | Coloque aqui o `Medicaldataset.csv` |

## Como executar (Windows, CMD)

Requer Python 3.10+. Coloque o `Medicaldataset.csv` em `dados\` e rode:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
run_all.bat
```

Ou passo a passo:

```bat
python 01_etl_carga.py
python 02_validacao.py
python 03_gerar_relatorio.py
```

O relatório só é gerado se a base for o `Medicaldataset.csv` com 1.319 linhas.

## Saídas

- `banco/datamart_cardiaco.sqlite` — banco populado (validação local)
- `sql/02_carga_dados.sql` — INSERTs em SQL padrão (PostgreSQL/MySQL/SQLite)
- `dados/registros_rejeitados.csv` e `dados/etl_log.json` — auditoria do ETL
- `resultados/` — consultas, resultados da validação e gráficos
- `Relatorio_Final_DataMart_Cardiaco.pdf` — relatório final

## Carga em outro banco (ex.: PostgreSQL)

1. Execute `sql/01_ddl_datamart.sql`.
2. Execute `sql/02_carga_dados.sql` (dimensões primeiro, fato por último).
3. Execute `resultados/consultas.sql` para validar.
