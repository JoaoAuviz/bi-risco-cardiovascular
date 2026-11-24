# -*- coding: utf-8 -*-
"""
Modelos de classificacao (Regressao Logistica e Random Forest) treinados a partir
do Data Mart: os dados sao lidos por JOIN entre a fato e as dimensoes.

Saidas: resultados/ml.json, graficos PNG em resultados/ e modelos/*.pkl
"""
import json
import sqlite3
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
OUT = BASE / "resultados"
(BASE / "modelos").mkdir(exist_ok=True)
SEED = 42

SQL = """
SELECT p.idade, p.genero, c.frequencia_cardiaca, c.pressao_sistolica, c.pressao_diastolica,
       f.glicemia, f.ck_mb, f.troponina, f.resultado
  FROM fato_exames_cardiacos f
  JOIN dim_paciente p ON f.id_paciente = p.id_paciente
  JOIN dim_clinica c ON f.id_clinica = c.id_clinica
 ORDER BY f.id_exame"""
con = sqlite3.connect(BASE / "banco" / "datamart_cardiaco.sqlite")
df = pd.read_sql_query(SQL, con)
con.close()

X, y = df.drop(columns="resultado"), df["resultado"]
NOMES = {"idade": "Idade", "genero": "Gênero", "frequencia_cardiaca": "Freq. cardíaca",
         "pressao_sistolica": "Pressão sistólica", "pressao_diastolica": "Pressão diastólica",
         "glicemia": "Glicemia", "ck_mb": "CK-MB", "troponina": "Troponina"}

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
modelos = {
    "Regressão Logística": make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEED)),
    "Random Forest": make_pipeline(
        StandardScaler(), RandomForestClassifier(class_weight="balanced", random_state=SEED)),
}
res = {"n_total": len(df), "n_treino": len(X_tr), "n_teste": len(X_te),
       "teste_positivos": int(y_te.sum()), "teste_negativos": int((y_te == 0).sum()),
       "modelos": {}}
roc = {}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
for nome, pipe in modelos.items():
    pipe.fit(X_tr, y_tr)  # o StandardScaler e ajustado apenas no treino (sem vazamento)
    pred = pipe.predict(X_te)
    prob = pipe.predict_proba(X_te)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y_te, pred).ravel()
    cvr = cross_validate(pipe, X, y, cv=cv, scoring=["accuracy", "roc_auc"])
    res["modelos"][nome] = {
        "acuracia": accuracy_score(y_te, pred), "precisao": precision_score(y_te, pred),
        "recall": recall_score(y_te, pred), "f1": f1_score(y_te, pred),
        "auc": roc_auc_score(y_te, prob), "vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp),
        "cv_acuracia_media": cvr["test_accuracy"].mean(), "cv_acuracia_dp": cvr["test_accuracy"].std(),
        "cv_auc_media": cvr["test_roc_auc"].mean(), "cv_auc_dp": cvr["test_roc_auc"].std()}
    roc[nome] = roc_curve(y_te, prob)
    joblib.dump(pipe, BASE / "modelos" / ("regressao_logistica.pkl" if "Log" in nome else "random_forest.pkl"))

rf = modelos["Random Forest"].named_steps["randomforestclassifier"]
imp = sorted(zip(X.columns, rf.feature_importances_), key=lambda t: -t[1])
res["importancias"] = [[NOMES[k], float(v)] for k, v in imp]
(OUT / "ml.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- graficos ----------------
C0, C1 = "#2A6FB0", "#D9822B"
TXT, MUTED, GRID = "#1F2933", "#6B7785", "#E3E7EC"

fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.3), dpi=200)
for ax, (nome, m) in zip(axs, res["modelos"].items()):
    mat = np.array([[m["vn"], m["fp"]], [m["fn"], m["vp"]]])
    ax.imshow(mat, cmap="Blues", vmin=0, vmax=mat.max() * 1.15)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(mat[i, j]), ha="center", va="center", fontsize=13,
                    color="white" if mat[i, j] > mat.max() * 0.5 else TXT)
    ax.set_xticks([0, 1], ["Previsto −", "Previsto +"], fontsize=8)
    ax.set_yticks([0, 1], ["Real −", "Real +"], fontsize=8)
    ax.set_title(f"{nome}\nAcurácia: {m['acuracia'] * 100:.1f}%".replace(".", ","), fontsize=9,
                 color=TXT)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "ml_matrizes_confusao.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=200)
for (nome, (fpr, tpr, _)), cor in zip(roc.items(), (C0, C1)):
    ax.plot(fpr, tpr, color=cor, lw=2,
            label=f"{nome} (AUC = {res['modelos'][nome]['auc']:.3f})".replace(".", ","))
ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--", label="Acaso (AUC = 0,500)")
ax.set_xlabel("Taxa de falsos positivos", fontsize=8, color=MUTED)
ax.set_ylabel("Taxa de verdadeiros positivos", fontsize=8, color=MUTED)
ax.tick_params(colors=TXT, labelsize=8, length=0)
ax.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "ml_curva_roc.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
nomes = [k for k, _ in res["importancias"]][::-1]
vals = [v for _, v in res["importancias"]][::-1]
bars = ax.barh(nomes, vals, color=C0, height=0.6)
for b, v in zip(bars, vals):
    ax.text(v + max(vals) * 0.01, b.get_y() + b.get_height() / 2,
            f"{v * 100:.1f}%".replace(".", ","), va="center", fontsize=8, color=TXT)
ax.set_xlim(0, max(vals) * 1.15)
ax.set_xlabel("Importância relativa (Random Forest)", fontsize=8, color=MUTED)
ax.tick_params(colors=TXT, labelsize=8, length=0)
ax.xaxis.grid(True, color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "ml_importancia_variaveis.png")
plt.close(fig)

print(json.dumps(res, ensure_ascii=False, indent=2))
