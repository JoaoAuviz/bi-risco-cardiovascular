# -*- coding: utf-8 -*-
"""
ETL do Data Mart de Exames Cardiacos (esquema estrela).

Extrai o Medicaldataset.csv, limpa e transforma os dados e carrega
dim_paciente, dim_clinica e fato_exames_cardiacos.

Uso:
    python 01_etl_carga.py                      # le dados/Medicaldataset.csv
    python 01_etl_carga.py caminho/arquivo.csv  # outra base (ex.: teste)

Saidas:
    banco/datamart_cardiaco.sqlite   banco populado (validacao)
    sql/02_carga_dados.sql           INSERTs em SQL padrao (PostgreSQL/MySQL/SQLite)
    dados/registros_rejeitados.csv   registros descartados e o motivo
    dados/etl_log.json               contagens de cada etapa
"""
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "dados" / "Medicaldataset.csv"
DDL = BASE / "sql" / "01_ddl_datamart.sql"
DB = BASE / "banco" / "datamart_cardiaco.sqlite"
SQL_CARGA = BASE / "sql" / "02_carga_dados.sql"
(BASE / "banco").mkdir(exist_ok=True)

if not CSV.exists():
    sys.exit(f"Arquivo de origem nao encontrado: {CSV}\n"
             "Coloque o Medicaldataset.csv na pasta dados/ e execute novamente.")

log = {"arquivo_origem": CSV.name,
       "sha256_origem": hashlib.sha256(CSV.read_bytes()).hexdigest()}

# ======================================================================
# 1. EXTRACT
# ======================================================================
# sep=None detecta o delimitador (a base usa ';'); tudo como texto para
# que a conversao fique sob controle do codigo.
bruto = pd.read_csv(CSV, sep=None, engine="python", dtype=str,
                    keep_default_na=False, encoding="utf-8-sig")
bruto.columns = [c.strip() for c in bruto.columns]
log["linhas_lidas"] = len(bruto)

MAPA_COLUNAS = {
    "age": "idade", "gender": "genero", "heart rate": "frequencia_cardiaca",
    "systolic blood pressure": "pressao_sistolica",
    "diastolic blood pressure": "pressao_diastolica", "blood sugar": "glicemia",
    "ck-mb": "ck_mb", "troponin": "troponina", "result": "resultado",
}
renomear = {c: MAPA_COLUNAS[c.lower()] for c in bruto.columns if c.lower() in MAPA_COLUNAS}
faltando = set(MAPA_COLUNAS.values()) - set(renomear.values())
if faltando:
    sys.exit(f"Colunas esperadas ausentes: {sorted(faltando)}. Colunas lidas: {list(bruto.columns)}")
df = bruto.rename(columns=renomear)[list(MAPA_COLUNAS.values())].copy()
df.insert(0, "linha_origem", range(2, len(df) + 2))  # linha no arquivo (1 = cabecalho)

# ======================================================================
# 2. TRANSFORM
# ======================================================================
NUMERICAS = ["idade", "genero", "frequencia_cardiaca", "pressao_sistolica",
             "pressao_diastolica", "glicemia", "ck_mb", "troponina"]
for c in NUMERICAS:  # virgula decimal -> ponto; nao numerico vira NaN
    df[c] = pd.to_numeric(df[c].str.strip().str.replace(",", ".", regex=False), errors="coerce")

# Variavel-alvo: positive = 1, negative = 0
df["resultado"] = df["resultado"].str.strip().str.lower().map(
    {"positive": 1, "negative": 0, "1": 1, "0": 0})

rejeitadas = []


def rejeitar(mascara, motivo):
    """Move linhas para a lista de rejeitadas e as remove de df."""
    global df
    if mascara.any():
        r = df[mascara].copy()
        r["motivo_rejeicao"] = motivo
        rejeitadas.append(r)
        df = df[~mascara].copy()


# 2.1 Valores nulos / nao numericos (dropna)
rejeitar(df[NUMERICAS + ["resultado"]].isna().any(axis=1), "valor ausente ou nao numerico")

# 2.2 Registros duplicados (todas as colunas identicas)
dup = df.duplicated(subset=NUMERICAS + ["resultado"], keep="first")
log["duplicados_removidos"] = int(dup.sum())
rejeitar(dup, "registro duplicado")

# 2.3 Regras de dominio (as mesmas restricoes CHECK do DDL)
inteiros = ["idade", "genero", "frequencia_cardiaca", "pressao_sistolica", "pressao_diastolica"]
nao_inteiro = (df[inteiros] % 1 != 0).any(axis=1)
rejeitar(nao_inteiro, "valor nao inteiro em campo inteiro")
rejeitar(~df["genero"].isin([0, 1]), "genero fora de {0,1}")
rejeitar(~((df["idade"] > 0) & (df["idade"] < 130)), "idade fora de 1-129")
rejeitar((df[["frequencia_cardiaca", "pressao_sistolica", "pressao_diastolica"]] <= 0).any(axis=1),
         "sinal vital <= 0")
rejeitar((df[["glicemia", "ck_mb", "troponina"]] < 0).any(axis=1), "biomarcador negativo")

# 2.4 Valores atipicos: sinalizados e MANTIDOS (nao violam o dominio do DDL)
atip = ((df["frequencia_cardiaca"] > 220) | (df["frequencia_cardiaca"] < 20) |
        (df["pressao_sistolica"] > 300) | (df["pressao_diastolica"] > 200))
log["atipicos_sinalizados_mantidos"] = int(atip.sum())

# 2.5 Precisao dos tipos NUMERIC do DDL (glicemia 2, ck_mb 3, troponina 4 casas)
log["perda_de_precisao_por_arredondamento"] = int(
    ((df["glicemia"].round(2) != df["glicemia"]) | (df["ck_mb"].round(3) != df["ck_mb"]) |
     (df["troponina"].round(4) != df["troponina"])).sum())
df["glicemia"] = df["glicemia"].round(2)
df["ck_mb"] = df["ck_mb"].round(3)
df["troponina"] = df["troponina"].round(4)
for c in inteiros + ["resultado"]:
    df[c] = df[c].astype(int)

if rejeitadas:
    rej = pd.concat(rejeitadas)
    rej_orig = bruto.iloc[rej["linha_origem"].values - 2].copy()
    rej_orig["linha_origem"] = rej["linha_origem"].values
    rej_orig["motivo_rejeicao"] = rej["motivo_rejeicao"].values
else:
    rej_orig = pd.DataFrame(columns=list(bruto.columns) + ["linha_origem", "motivo_rejeicao"])
rej_orig.to_csv(BASE / "dados" / "registros_rejeitados.csv", sep=";", index=False, encoding="utf-8")
log["rejeitadas_total"] = len(rej_orig)
log["rejeitadas_por_motivo"] = rej_orig["motivo_rejeicao"].value_counts().to_dict()
log["linhas_validas"] = len(df)
log["classes_origem_validas"] = {"positivos": int(df["resultado"].sum()),
                                 "negativos": int((df["resultado"] == 0).sum())}
df = df.reset_index(drop=True)

# 2.6 Dimensoes: combinacoes distintas dos atributos (chave substituta sequencial)
dim_paciente = df[["idade", "genero"]].drop_duplicates().sort_values(["idade", "genero"]) \
    .reset_index(drop=True)
dim_paciente.insert(0, "id_paciente", range(1, len(dim_paciente) + 1))

dim_clinica = df[["frequencia_cardiaca", "pressao_sistolica", "pressao_diastolica"]] \
    .drop_duplicates().sort_values(["frequencia_cardiaca", "pressao_sistolica", "pressao_diastolica"]) \
    .reset_index(drop=True)
dim_clinica.insert(0, "id_clinica", range(1, len(dim_clinica) + 1))

# 2.7 Fato: um registro por exame (substitui valores de negocio pelas chaves)
fato = df.merge(dim_paciente, on=["idade", "genero"], how="left") \
         .merge(dim_clinica, on=["frequencia_cardiaca", "pressao_sistolica", "pressao_diastolica"],
                how="left")
fato.insert(0, "id_exame", range(1, len(fato) + 1))
fato = fato[["id_exame", "id_paciente", "id_clinica", "glicemia", "ck_mb", "troponina", "resultado"]]

tabelas = [("dim_paciente", dim_paciente), ("dim_clinica", dim_clinica),
           ("fato_exames_cardiacos", fato)]  # dimensoes primeiro, fato por ultimo

# ======================================================================
# 3. LOAD
# ======================================================================
def linhas(frame):
    return frame.astype(object).where(frame.notna(), None).values.tolist()


if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON")
con.executescript(DDL.read_text(encoding="utf-8"))
for nome, frame in tabelas:
    cols = ", ".join(frame.columns)
    con.executemany(f"INSERT INTO {nome} ({cols}) VALUES ({', '.join('?' * len(frame.columns))})",
                    linhas(frame))
con.commit()
log["carregado"] = {n: con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n, _ in tabelas}
con.close()


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return repr(v)
    return str(v)


with open(SQL_CARGA, "w", encoding="utf-8") as f:
    f.write("-- Carga gerada por 01_etl_carga.py. Executar APOS sql/01_ddl_datamart.sql.\n\n")
    for nome, frame in tabelas:
        cols = ", ".join(frame.columns)
        rows = ["(" + ", ".join(lit(v) for v in r) + ")" for r in linhas(frame)]
        for i in range(0, len(rows), 500):
            f.write(f"INSERT INTO {nome} ({cols}) VALUES\n" + ",\n".join(rows[i:i + 500]) + ";\n")
        f.write("\n")

(BASE / "dados" / "etl_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=2))
