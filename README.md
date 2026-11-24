# Data Mart de Exames Cardíacos — ETL, validação e modelos de ML

Trabalho final do CONIC-SEMESP — FATEC Bauru, Análise e Desenvolvimento de Sistemas.

- **Autor:** João Gabriel Alves Lima
- **Orientação:** Profa. Dra. Patricia Bellin Ribeiro
- **Relatório final (PDF):** [`docs/Relatorio_Final_DataMart_Cardiaco.pdf`](docs/Relatorio_Final_DataMart_Cardiaco.pdf)

Pipeline em Python que lê o `Medicaldataset.csv` (Kaggle, 1.319 registros), limpa e
transforma os dados e carrega um **esquema estrela**: `fato_exames_cardiacos` +
`dim_paciente` + `dim_clinica`. Inclui validação da carga e duas necessidades do gestor
(uma fato e uma dimensão: `fato_exames_cardiacos` e `dim_paciente`). Os dados do Data Mart
alimentam dois classificadores (Regressão Logística e Random Forest).

## Estrutura

| Caminho | Função |
|---|---|
| `sql/01_ddl_datamart.sql` | DDL do Data Mart (Anexo A da Entrega Parcial 1) |
| `01_etl_carga.py` | Extração, limpeza, transformação e carga |
| `02_validacao.py` | Contagens, integridade, testes de restrição e consultas do gestor |
| `03_modelos_ml.py` | Lê o Data Mart por JOIN, treina e avalia os modelos, salva os `.pkl` |
| `04_gerar_relatorio.py` | Gera o relatório PDF (ABNT) a partir dos resultados |
| `dados/Medicaldataset.csv` | Base de origem (já incluída) |
| `tools/gerar_base_teste.py` | Gera base sintética **apenas para testar** o pipeline |
| `docs/` | Relatório final em PDF |

## Como executar (Windows, CMD)

Requer Python 3.10 ou superior. A base já está na pasta `dados\`.

```bat
git clone https://github.com/JoaoAuviz/bi-risco-cardiovascular.git
cd bi-risco-cardiovascular
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
run_all.bat
```

Ou etapa por etapa:

```bat
python 01_etl_carga.py
python 02_validacao.py
python 03_modelos_ml.py
python 04_gerar_relatorio.py
```

O relatório só é gerado se a base for o `Medicaldataset.csv` com 1.319 linhas.

## Saídas geradas ao executar

- `banco/datamart_cardiaco.sqlite` — banco populado (validação local; não é versionado)
- `sql/02_carga_dados.sql` — INSERTs em SQL padrão (PostgreSQL, MySQL, SQLite)
- `dados/registros_rejeitados.csv` e `dados/etl_log.json` — auditoria do ETL
- `modelos/` — `regressao_logistica.pkl` e `random_forest.pkl`
- `resultados/` — consultas, validação, métricas (`ml.json`) e gráficos
- `Relatorio_Final_DataMart_Cardiaco.pdf` — gerado na raiz; a versão entregue está em `docs/`

## Carga em outro banco (ex.: PostgreSQL)

1. Execute `sql/01_ddl_datamart.sql`.
2. Execute `sql/02_carga_dados.sql` (dimensões primeiro, fato por último).
3. Execute `resultados/consultas.sql` para validar.
