# -*- coding: utf-8 -*-
"""
Validacao da carga + duas necessidades do gestor (1 fato + 1 dimensao).

Fato: fato_exames_cardiacos | Dimensao: dim_paciente

Saidas em resultados/: validacao.json, consultas.sql, graficos PNG.
"""
import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
OUT = BASE / "resultados"
OUT.mkdir(exist_ok=True)
log = json.loads((BASE / "dados" / "etl_log.json").read_text(encoding="utf-8"))

FAIXA = ("CASE WHEN p.idade < 40 THEN '1) ate 39' WHEN p.idade < 50 THEN '2) 40-49' "
         "WHEN p.idade < 60 THEN '3) 50-59' WHEN p.idade < 70 THEN '4) 60-69' ELSE '5) 70+' END")

QUERIES = {
    "V1_contagem_registros": """
        SELECT 'dim_paciente' AS tabela, COUNT(*) AS registros FROM dim_paciente
        UNION ALL SELECT 'dim_clinica', COUNT(*) FROM dim_clinica
        UNION ALL SELECT 'fato_exames_cardiacos', COUNT(*) FROM fato_exames_cardiacos""",
    "V2_integridade_referencial": """
        SELECT 'dim_paciente' AS dimensao, COUNT(*) AS fatos_orfaos
          FROM fato_exames_cardiacos f
          LEFT JOIN dim_paciente d ON f.id_paciente = d.id_paciente
         WHERE d.id_paciente IS NULL
        UNION ALL SELECT 'dim_clinica', COUNT(*)
          FROM fato_exames_cardiacos f
          LEFT JOIN dim_clinica d ON f.id_clinica = d.id_clinica
         WHERE d.id_clinica IS NULL""",
    "V3_distribuicao_resultado": """
        SELECT SUM(CASE WHEN resultado = 1 THEN 1 ELSE 0 END) AS positivos,
               SUM(CASE WHEN resultado = 0 THEN 1 ELSE 0 END) AS negativos,
               COUNT(*) AS total
          FROM fato_exames_cardiacos""",
    "V4_amostra_juncao": """
        SELECT f.id_exame, p.idade, p.genero, c.frequencia_cardiaca,
               c.pressao_sistolica, c.pressao_diastolica,
               f.glicemia, f.ck_mb, f.troponina, f.resultado
          FROM fato_exames_cardiacos f
          JOIN dim_paciente p ON f.id_paciente = p.id_paciente
          JOIN dim_clinica c ON f.id_clinica = c.id_clinica
         ORDER BY f.id_exame
         LIMIT 5""",
    "N1_positividade_por_faixa_e_genero": f"""
        SELECT {FAIXA} AS faixa_etaria, p.genero,
               COUNT(*) AS exames,
               SUM(f.resultado) AS positivos,
               ROUND(100.0 * SUM(f.resultado) / COUNT(*), 1) AS pct_positivos
          FROM fato_exames_cardiacos f
          JOIN dim_paciente p ON f.id_paciente = p.id_paciente
         GROUP BY faixa_etaria, p.genero
         ORDER BY faixa_etaria, p.genero""",
    "N2_biomarcadores_por_faixa_e_resultado": f"""
        SELECT {FAIXA} AS faixa_etaria, f.resultado,
               COUNT(*) AS exames,
               ROUND(AVG(f.troponina), 3) AS troponina_media,
               ROUND(AVG(f.ck_mb), 2) AS ck_mb_media,
               ROUND(AVG(f.glicemia), 1) AS glicemia_media
          FROM fato_exames_cardiacos f
          JOIN dim_paciente p ON f.id_paciente = p.id_paciente
         GROUP BY faixa_etaria, f.resultado
         ORDER BY faixa_etaria, f.resultado""",
}

DB = BASE / "banco" / "datamart_cardiaco.sqlite"
con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON")
res = {}
for nome, sql in QUERIES.items():
    cur = con.execute(sql)
    res[nome] = {"sql": " ".join(sql.split()), "colunas": [c[0] for c in cur.description],
                 "linhas": cur.fetchall()}
res["fk_check"] = con.execute("PRAGMA foreign_key_check").fetchall()

# Teste negativo: as restricoes do DDL rejeitam dados invalidos? (copia em memoria)
mem = sqlite3.connect(":memory:")
con.backup(mem)
con.close()
mem.execute("PRAGMA foreign_keys = ON")
testes = []
for desc, sql in [
    ("exame referenciando paciente inexistente",
     "INSERT INTO fato_exames_cardiacos VALUES (999999, 999999, 1, 100, 1, 0.01, 0)"),
    ("genero fora do dominio {0,1}", "INSERT INTO dim_paciente VALUES (999999, 50, 7)"),
    ("resultado fora do dominio {0,1}",
     "INSERT INTO fato_exames_cardiacos VALUES (999998, 1, 1, 100, 1, 0.01, 5)"),
]:
    try:
        mem.execute(sql)
        testes.append([desc, "ACEITO (falha)"])
    except sqlite3.IntegrityError as e:
        testes.append([desc, "rejeitado: " + str(e)])
mem.close()
res["V5_testes_restricoes"] = {"colunas": ["tentativa", "resultado"], "linhas": testes}

# Reconciliacao com o log do ETL
cont = dict(res["V1_contagem_registros"]["linhas"])
pos, neg, tot = res["V3_distribuicao_resultado"]["linhas"][0]
res["reconciliacao"] = {
    "fato_igual_linhas_validas": cont["fato_exames_cardiacos"] == log["linhas_validas"],
    "classes_iguais_ao_etl": (pos, neg) == (log["classes_origem_validas"]["positivos"],
                                            log["classes_origem_validas"]["negativos"]),
    "orfaos_zero": all(r[1] == 0 for r in res["V2_integridade_referencial"]["linhas"]),
    "fk_check_vazio": res["fk_check"] == [],
}
assert all(res["reconciliacao"].values()), res["reconciliacao"]

(OUT / "validacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "consultas.sql").write_text(
    "-- Consultas de validacao e das necessidades do gestor (SQL padrao)\n\n" +
    "\n\n".join(f"-- {k}\n{v['sql']};" for k, v in res.items() if isinstance(v, dict) and "sql" in v),
    encoding="utf-8")

# ---------------- graficos (2 series, legenda + rotulos diretos) ----------------
C0, C1 = "#2A6FB0", "#D9822B"
TXT, MUTED, GRID = "#1F2933", "#6B7785", "#E3E7EC"


def estilo(ax, titulo, ylabel):
    ax.set_title(titulo, fontsize=10, color=TXT, loc="left", pad=10)
    ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
    ax.tick_params(colors=TXT, labelsize=8, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def grupos(rows, ki, kv, vi):
    faixas = sorted({r[0] for r in rows})
    chaves = sorted({r[ki] for r in rows})
    d = {(r[0], r[ki]): r[vi] for r in rows}
    return faixas, chaves, d


rows = res["N1_positividade_por_faixa_e_genero"]["linhas"]
faixas, gens, d = grupos(rows, 1, None, 4)
fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
w = 0.38
for i, (g, cor) in enumerate(zip(gens, (C0, C1))):
    xs = [k + (i - 0.5) * w for k in range(len(faixas))]
    vs = [d.get((f, g), 0) for f in faixas]
    bars = ax.bar(xs, vs, w * 0.92, color=cor, label=f"Gênero {g}")
    for b, v in zip(bars, vs):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}".replace(".", ",") + "%",
                ha="center", fontsize=7, color=TXT)
ax.set_xticks(range(len(faixas)))
ax.set_xticklabels([f.split(") ")[1] for f in faixas])
ax.set_ylim(0, 112)
estilo(ax, "Percentual de resultados positivos por faixa etária e gênero", "% de exames positivos")
ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
fig.tight_layout()
fig.savefig(OUT / "grafico_positividade.png")
plt.close(fig)

rows = res["N2_biomarcadores_por_faixa_e_resultado"]["linhas"]
faixas, rs, d = grupos(rows, 1, None, 3)
fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
for i, (r, cor, nome) in enumerate(zip(rs, (C0, C1), ("Negativo", "Positivo"))):
    xs = [k + (i - 0.5) * w for k in range(len(faixas))]
    vs = [d.get((f, r), 0) for f in faixas]
    bars = ax.bar(xs, vs, w * 0.92, color=cor, label=nome)
    for b, v in zip(bars, vs):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}".replace(".", ","), ha="center",
                va="bottom", fontsize=7, color=TXT)
ax.set_xticks(range(len(faixas)))
ax.set_xticklabels([f.split(") ")[1] for f in faixas])
ax.set_ylim(0, max(d.values()) * 1.18)
estilo(ax, "Troponina média por faixa etária e resultado do exame", "Troponina média")
ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
fig.tight_layout()
fig.savefig(OUT / "grafico_troponina.png")
plt.close(fig)

for k, v in res.items():
    if isinstance(v, dict) and "colunas" in v:
        print("##", k, v["colunas"])
        for r in v["linhas"]:
            print("  ", r)
print("reconciliacao:", res["reconciliacao"])
