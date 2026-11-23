# -*- coding: utf-8 -*-
"""
Gera uma base SINTETICA com o mesmo esquema do Medicaldataset.csv, apenas para
testar o pipeline quando a base real nao esta disponivel.
NAO usar nos resultados do relatorio.

Uso: python tools/gerar_base_teste.py saida.csv
"""
import csv
import random
import sys

random.seed(7)
saida = sys.argv[1] if len(sys.argv) > 1 else "Medicaldataset_teste.csv"
cab = ["Age", "Gender", "Heart rate", "Systolic blood pressure", "Diastolic blood pressure",
       "Blood sugar", "CK-MB", "Troponin", "Result"]
linhas = []
for _ in range(1319):
    pos = random.random() < 0.614
    idade = int(min(100, max(14, random.gauss(60 if pos else 52, 13))))
    fc = random.randint(45, 130)
    pas = random.randint(85, 200)
    pad = random.randint(45, 110)
    gl = round(random.uniform(70, 300), 1)
    ck = round(random.expovariate(1 / (6 if pos else 2)) + 0.3, 2)
    tr = round(random.expovariate(1 / (1.2 if pos else 0.02)) + 0.001, 3)
    linhas.append([idade, random.choice([0, 1]), fc, pas, pad, gl, ck, tr,
                   "positive" if pos else "negative"])
linhas[5][2] = 1111          # valor atipico
linhas[100][5] = ""          # nulo
linhas.append(list(linhas[20]))  # duplicado
with open(saida, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(cab)
    w.writerows(linhas)
print("Base de TESTE gerada:", saida, len(linhas), "linhas")
