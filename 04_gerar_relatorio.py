# -*- coding: utf-8 -*-
"""
Gera o relatorio final em PDF (padrao ABNT) a partir dos resultados REAIS do
ETL e da validacao. Os numeros do texto vem de dados/etl_log.json e
resultados/validacao.json: nada e digitado a mao.

Trava de seguranca: so gera o PDF final se a base for o Medicaldataset.csv com
1.319 linhas. Para testar com outra base: defina ALLOW_OTHER_BASE=1 (o PDF sai
marcado como "BASE DE TESTE").
"""
import json
import os
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                XPreformatted)
from reportlab.platypus.tableofcontents import TableOfContents

BASE = Path(__file__).resolve().parent
RES = BASE / "resultados"
val = json.loads((RES / "validacao.json").read_text(encoding="utf-8"))
log = json.loads((BASE / "dados" / "etl_log.json").read_text(encoding="utf-8"))
ml = json.loads((RES / "ml.json").read_text(encoding="utf-8"))

TESTE = False
if not (log["arquivo_origem"] == "Medicaldataset.csv" and log["linhas_lidas"] == 1319):
    if os.environ.get("ALLOW_OTHER_BASE") != "1":
        sys.exit("ERRO: a base usada no ETL nao e o Medicaldataset.csv com 1.319 linhas "
                 f"(lido: {log['arquivo_origem']}, {log['linhas_lidas']} linhas).\n"
                 "Coloque o arquivo real em dados/, rode 01_etl_carga.py e 02_validacao.py "
                 "e tente de novo.")
    TESTE = True

# Fatos extraidos do banco carregado, usados nas ressalvas do texto
import sqlite3
_c = sqlite3.connect(BASE / "banco" / "datamart_cardiaco.sqlite")
fc_max, n_fc = _c.execute(
    "SELECT MAX(c.frequencia_cardiaca), COUNT(*) FROM fato_exames_cardiacos f "
    "JOIN dim_clinica c ON f.id_clinica = c.id_clinica WHERE c.frequencia_cardiaca > 220").fetchone()
_ck = sorted(r[0] for r in _c.execute("SELECT ck_mb FROM fato_exames_cardiacos"))
_c.close()
ck_med, ck_max, ck_n50 = _ck[len(_ck) // 2], _ck[-1], sum(1 for v in _ck if v > 50)

# ----------------------------------------------------------------------------
# Estilos (ABNT: A4, margens 3/3/2/2 cm, fonte 12, entrelinhas 1,5)
# ----------------------------------------------------------------------------
TXT, TXTB = "Times-Roman", "Times-Bold"
corpo = ParagraphStyle("corpo", fontName=TXT, fontSize=12, leading=18, alignment=TA_JUSTIFY,
                       firstLineIndent=1.25 * cm)
corpo_si = ParagraphStyle("corpo_si", parent=corpo, firstLineIndent=0)
h1 = ParagraphStyle("H1", fontName=TXTB, fontSize=12, leading=18, spaceBefore=18, spaceAfter=18,
                    keepWithNext=1)
h1c = ParagraphStyle("H1c", parent=h1, alignment=TA_CENTER)
h1s = ParagraphStyle("H1s", parent=h1, alignment=TA_CENTER)
h2 = ParagraphStyle("H2", fontName=TXTB, fontSize=12, leading=18, spaceBefore=12, spaceAfter=12,
                    keepWithNext=1)
legenda = ParagraphStyle("legenda", fontName=TXT, fontSize=10, leading=12, spaceBefore=6, spaceAfter=4)
fonte = ParagraphStyle("fonte", fontName=TXT, fontSize=10, leading=12, spaceBefore=3, spaceAfter=12)
cel = ParagraphStyle("cel", fontName=TXT, fontSize=10, leading=12, alignment=TA_LEFT)
celb = ParagraphStyle("celb", parent=cel, fontName=TXTB)
celr = ParagraphStyle("celr", parent=cel, alignment=2)
celrb = ParagraphStyle("celrb", parent=celr, fontName=TXTB)
code = ParagraphStyle("code", fontName="Courier", fontSize=7, leading=8.8,
                      backColor=colors.HexColor("#F3F4F6"), borderColor=colors.HexColor("#C9D0D8"),
                      borderWidth=0.5, borderPadding=4, spaceBefore=4, spaceAfter=4)
capa_c = ParagraphStyle("capa_c", fontName=TXTB, fontSize=12, leading=18, alignment=TA_CENTER)
capa_t = ParagraphStyle("capa_t", parent=capa_c, fontSize=14, leading=20)
nat = ParagraphStyle("nat", fontName=TXT, fontSize=10, leading=12, alignment=TA_JUSTIFY, leftIndent=8 * cm)
ref = ParagraphStyle("ref", fontName=TXT, fontSize=12, leading=14, alignment=TA_LEFT, spaceAfter=14)
toc1 = ParagraphStyle("toc1", fontName=TXTB, fontSize=12, leading=18)
toc2 = ParagraphStyle("toc2", fontName=TXT, fontSize=12, leading=18, leftIndent=0.8 * cm)


def P(t, st=corpo):
    return Paragraph(t, st)


def num(n):
    return f"{n:,}".replace(",", ".")


def dec(v, c=2):
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def trecho(ini, fim=None, largura=108, arq="01_etl_carga.py"):
    linhas = (BASE / arq).read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(linhas) if l.startswith(ini))
    j = next(k for k in range(i + 1, len(linhas)) if linhas[k].startswith(fim)) if fim else len(linhas)
    bloco = linhas[i:j]
    while bloco and not bloco[-1].strip():
        bloco.pop()
    return "\n".join(bloco)


def codigo(txt, largura=108):
    saida = []
    for l in txt.split("\n"):
        if len(l) <= largura:
            saida.append(l)
        else:
            ind = len(l) - len(l.lstrip())
            saida.extend(textwrap.wrap(l, largura, subsequent_indent=" " * (ind + 4),
                                       break_long_words=True, replace_whitespace=False))
    return XPreformatted(escape("\n".join(saida)), code)


def tabela(cab, linhas, larg, direita=()):
    dados = [[Paragraph(c, celrb if i in direita else celb) for i, c in enumerate(cab)]]
    for l in linhas:
        dados.append([Paragraph(str(c), celr if i in direita else cel) for i, c in enumerate(l)])
    t = Table(dados, colWidths=[w * cm for w in larg], repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def bloco_tabela(titulo, t, f="Fonte: Elaborado pelo autor (2026)."):
    return KeepTogether([P(titulo, legenda), t, P(f, fonte)])


def bloco_figura(titulo, arq, larg=15.5, f="Fonte: Elaborado pelo autor (2026)."):
    w, h = PILImage.open(arq).size
    return KeepTogether([P(titulo, legenda), Image(str(arq), width=larg * cm, height=larg * cm * h / w),
                         P(f, fonte)])


def sql_q(chave):
    s = val[chave]["sql"]
    for a, b in ((" FROM ", "\n  FROM "), (" JOIN ", "\n  JOIN "), (" LEFT JOIN ", "\n  LEFT JOIN "),
                 (" WHERE ", "\n WHERE "), (" GROUP BY ", "\n GROUP BY "), (" ORDER BY ", "\n ORDER BY "),
                 (" UNION ALL ", "\nUNION ALL\n"), (" LIMIT ", "\n LIMIT ")):
        s = s.replace(a, b)
    return s + ";"


# ----------------------------------------------------------------------------
class Doc(BaseDocTemplate):
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H1c", "H2"):
            self.notify("TOCEntry", (1 if f.style.name == "H2" else 0, f.getPlainText(), self.page))


def num_pagina(canv, doc):
    canv.saveState()
    canv.setFont(TXT, 10)
    canv.drawRightString(A4[0] - 2 * cm, A4[1] - 1.5 * cm, str(doc.page))
    if TESTE:
        canv.setFillColor(colors.red)
        canv.setFont(TXTB, 10)
        canv.drawString(3 * cm, A4[1] - 1.5 * cm, "BASE DE TESTE - NAO ENTREGAR")
    canv.restoreState()


OUT_PDF = BASE / ("RASCUNHO_BASE_DE_TESTE.pdf" if TESTE else "Relatorio_Final_DataMart_Cardiaco.pdf")
TITULO = ("DATA MART EM ESQUEMA ESTRELA, ETL E APRENDIZADO DE MÁQUINA PARA CLASSIFICAÇÃO DE "
          "RISCO CARDIOVASCULAR")
doc = Doc(str(OUT_PDF), pagesize=A4, leftMargin=3 * cm, rightMargin=2 * cm, topMargin=3 * cm,
          bottomMargin=2 * cm, title=TITULO.title(), author="João Gabriel Alves Lima")
fr = Frame(3 * cm, 2 * cm, 16 * cm, 24.7 * cm, id="f", leftPadding=0, rightPadding=0, topPadding=0,
           bottomPadding=0)
doc.addPageTemplates([PageTemplate("front", [fr]), PageTemplate("main", [fr], onPage=num_pagina)])

AUTOR = "João Gabriel Alves Lima"
INST = "FACULDADE DE TECNOLOGIA (FATEC) DE BAURU"
CURSO = "CURSO DE ANÁLISE E DESENVOLVIMENTO DE SISTEMAS"
PROF = "Profa. Dra. Patricia Bellin Ribeiro"

# Figura 1 (da Entrega Parcial 1) sem as margens brancas
from PIL import ImageChops
_im = PILImage.open(BASE / "assets" / "fig-000.png").convert("RGB")
_bb = ImageChops.difference(_im, PILImage.new("RGB", _im.size, (255, 255, 255))).getbbox()
_im.crop((max(_bb[0] - 20, 0), max(_bb[1] - 20, 0), _bb[2] + 20, _bb[3] + 20)).save(
    BASE / "assets" / "fig1_recortada.png")
FIG1 = BASE / "assets" / "fig1_recortada.png"

S = []
S += [P(INST, capa_c), P(CURSO, capa_c), Spacer(1, 3.2 * cm), P(AUTOR.upper(), capa_c),
      Spacer(1, 4.5 * cm), P(TITULO, capa_t), Spacer(1, 7.4 * cm), P("BAURU", capa_c), P("2026", capa_c),
      PageBreak()]
S += [P(AUTOR.upper(), capa_c), Spacer(1, 4.5 * cm), P(TITULO, capa_t), Spacer(1, 3.2 * cm),
      P("Trabalho final desenvolvido para o CONIC-SEMESP, consolidando as etapas de modelagem "
        "multidimensional e de programação e carga de dados do projeto de Business Intelligence.", nat),
      Spacer(1, 0.6 * cm), P("Orientação: " + PROF, nat), Spacer(1, 6.2 * cm),
      P("BAURU", capa_c), P("2026", capa_c), PageBreak()]
S += [P("SUMÁRIO", h1s)]
toc = TableOfContents()
toc.levelStyles = [toc1, toc2]
S += [toc, NextPageTemplate("main"), PageBreak()]

N = log["linhas_lidas"]
V = log["linhas_validas"]
car = log["carregado"]
cl = log["classes_origem_validas"]
mot = log["rejeitadas_por_motivo"]

# ============================================================================
S += [P("1 INTRODUÇÃO E OBJETIVOS", h1)]
S += [P("As doenças cardiovasculares estão entre as principais causas de morte no mundo, e eventos "
        "graves como o infarto agudo do miocárdio e a morte súbita frequentemente ocorrem sem que o "
        "paciente tenha sido identificado previamente como de alto risco (WORLD HEALTH ORGANIZATION, "
        "[s.d.]). Nesse cenário, a rapidez e a precisão na interpretação dos exames clínicos influenciam "
        "diretamente o desfecho do atendimento. Entre esses exames, os biomarcadores de lesão "
        "miocárdica, em especial a troponina cardíaca e a enzima CK-MB, ocupam papel central no "
        "diagnóstico do infarto (THYGESEN et al., 2018)."),
      P("A Inteligência Artificial e, mais especificamente, o Aprendizado de Máquina permitem "
        "identificar padrões em conjuntos de dados clínicos e oferecer apoio à decisão dos "
        "profissionais de saúde, sem substituir o julgamento médico (GÉRON, 2022). Para que esses algoritmos sejam "
        "aplicados de forma organizada e reprodutível, é desejável que os dados estejam estruturados "
        "em um ambiente analítico adequado, e não apenas em arquivos planos. Um Data Mart, "
        "subconjunto analítico voltado a um assunto específico, cumpre esse papel (INMON, 2005), e a "
        "modelagem multidimensional em esquema estrela organiza os dados em uma tabela fato, com as "
        "medidas dos eventos, ligada a tabelas dimensão, que descrevem o contexto (KIMBALL; ROSS, "
        "2013)."),
      P("A base de dados selecionada, Medicaldataset.csv, obtida na plataforma Kaggle (Heart Attack "
        "Analysis Dataset), reúne 1.319 registros de pacientes com informações demográficas (idade e "
        "gênero), sinais clínicos (frequência cardíaca e pressões arteriais sistólica e diastólica), "
        "glicemia e os biomarcadores CK-MB e troponina, além do resultado do exame (positivo ou "
        "negativo). A relevância da base está na combinação de medidas clínicas simples, facilmente "
        "obtidas em qualquer atendimento, com marcadores laboratoriais específicos de dano cardíaco."),
      P("O problema de negócio que orienta o projeto é o de classificar o risco cardíaco de um "
        "paciente a partir de seus exames clínicos. O projeto se organiza em duas frentes "
        "complementares: (i) a estruturação de um Data Mart em esquema estrela, com a engenharia de "
        "dados que o alimenta; e (ii) o desenvolvimento de modelos preditivos de classificação, que "
        "consomem os dados já estruturados no Data Mart."),
      P("O objetivo geral deste trabalho é projetar e alimentar um Data Mart em esquema estrela, por "
        "meio de um processo de ETL (Extract, Transform, Load), de modo que os dados de exames "
        "cardíacos fiquem íntegros e prontos para consumo analítico e para a criação de dashboards, e "
        "desenvolver, a partir deles, modelos de Aprendizado de Máquina que classifiquem o risco cardíaco. "
        "Os objetivos específicos são:"),
      P("a) programar a leitura, a limpeza e a transformação da base original;", corpo_si),
      P("b) carregar a tabela fato e as dimensões do Data Mart, respeitando a integridade "
        "referencial;", corpo_si),
      P("c) validar a carga por contagens, testes de integridade e reconciliação com o processo de "
        "ETL;", corpo_si),
      P("d) atender a duas necessidades do gestor utilizando uma tabela fato e uma dimensão: "
        "(1) identificar o perfil de idade e gênero dos exames com resultado positivo e "
        "(2) comparar o nível dos biomarcadores entre exames positivos e negativos por faixa etária;",
        corpo_si),
      P("e) treinar e comparar dois classificadores, Regressão Logística e Random Forest, usando os "
        "dados lidos do Data Mart, e identificar as variáveis de maior poder preditivo.", corpo_si)]

# ============================================================================
S += [P("2 MATERIAIS E MÉTODOS", h1)]
S += [P("2.1 Descrição técnica da base de dados", h2)]
S += [P("A base original é um arquivo de texto no formato CSV (Medicaldataset.csv), com colunas "
        "delimitadas por ponto e vírgula (;), contendo 1.319 registros e 9 colunas: oito variáveis "
        "preditoras e uma variável-alvo. A Tabela 1 apresenta o dicionário de dados e o destino de "
        "cada variável no Data Mart.")]
t1 = [["Age", "Idade do paciente", "Numérica inteira", "dim_paciente.idade"],
      ["Gender", "Gênero do paciente (codificado 0/1)", "Categórica binária", "dim_paciente.genero"],
      ["Heart rate", "Frequência cardíaca", "Numérica inteira", "dim_clinica.frequencia_cardiaca"],
      ["Systolic blood pressure", "Pressão arterial sistólica", "Numérica inteira",
       "dim_clinica.pressao_sistolica"],
      ["Diastolic blood pressure", "Pressão arterial diastólica", "Numérica inteira",
       "dim_clinica.pressao_diastolica"],
      ["Blood sugar", "Glicemia", "Numérica contínua", "fato_exames_cardiacos.glicemia"],
      ["CK-MB", "Enzima creatina quinase-MB (biomarcador cardíaco)", "Numérica contínua",
       "fato_exames_cardiacos.ck_mb"],
      ["Troponin", "Nível de troponina (biomarcador de necrose miocárdica)", "Numérica contínua",
       "fato_exames_cardiacos.troponina"],
      ["Result", "Variável-alvo: positivo (1) ou negativo (0)", "Categórica binária",
       "fato_exames_cardiacos.resultado"]]
S += [bloco_tabela("Tabela 1 – Dicionário de dados da base e mapeamento para o Data Mart",
                   tabela(["Variável original", "Descrição", "Tipo", "Destino no Data Mart"], t1,
                          [3.0, 4.2, 2.8, 6.0]))]

S += [P("2.2 Esquema do Data Mart", h2)]
S += [P("Adotou-se a modelagem multidimensional sob o esquema estrela (Star Schema), conforme "
        "Kimball e Ross (2013), na qual uma tabela fato central, que concentra as métricas "
        "quantitativas, se relaciona diretamente com tabelas dimensão. Em comparação ao esquema "
        "Snowflake, o esquema estrela evita a normalização das dimensões, reduzindo o número de "
        "junções e simplificando as consultas analíticas, o que é adequado ao volume e à estrutura "
        "desta base."),
      P("A granularidade da tabela fato é de um registro por exame cardíaco realizado. O modelo é "
        "composto por fato_exames_cardiacos (fato), que guarda as métricas glicemia, CK-MB e "
        "troponina, o indicador binário do resultado e as chaves estrangeiras; dim_paciente "
        "(dimensão), com idade e gênero; e dim_clinica (dimensão), com frequência cardíaca e pressões "
        "sistólica e diastólica. Dimensões como tempo e localização não foram incluídas porque a base "
        "de origem não possui campos de data nem de local. A Figura 1 apresenta o diagrama e a "
        "Tabela 2 resume os relacionamentos.")]
S += [bloco_figura("Figura 1 – Diagrama do Data Mart em esquema estrela", FIG1, 15.5)]
t2 = [["dim_paciente (1) e fato_exames_cardiacos (N)", "id_paciente (PK na dimensão; FK na fato)", "1:N"],
      ["dim_clinica (1) e fato_exames_cardiacos (N)", "id_clinica (PK na dimensão; FK na fato)", "1:N"]]
S += [bloco_tabela("Tabela 2 – Relacionamentos entre as tabelas do Data Mart",
                   tabela(["Relacionamento", "Chave", "Cardinalidade"], t2, [6.6, 6.6, 2.8]))]

S += [P("2.3 Infraestrutura técnica e construção física", h2)]
S += [P("A estrutura física foi criada por um script SQL em linguagem de definição de dados (DDL), "
        "escrito em SQL padrão, seguindo a sintaxe documentada pelo PostgreSQL (POSTGRESQL GLOBAL "
        "DEVELOPMENT GROUP, [s.d.]). O script contém: remoção prévia das tabelas (DROP TABLE IF "
        "EXISTS) em ordem inversa às dependências; chaves primárias inteiras (id_paciente, "
        "id_clinica e id_exame); chaves estrangeiras na tabela fato; tipos SMALLINT para idade, "
        "gênero, sinais vitais e resultado, e NUMERIC com precisão definida para glicemia, CK-MB e "
        "troponina, evitando erros de arredondamento de ponto flutuante; restrições NOT NULL e "
        "CHECK (gênero e resultado restritos a 0 ou 1, idade entre 1 e 129 anos e sinais vitais "
        "positivos); e índices sobre as chaves estrangeiras da fato."),
      P("O processo de ETL foi programado em Python 3, com a biblioteca pandas (MCKINNEY, 2018), em "
        "script desenvolvido para o Google Colab, ambiente utilizado nas etapas anteriores, e que também pode ser executado em máquina local. A carga e a "
        "validação foram executadas em um banco SQLite com a verificação de chaves estrangeiras "
        "ativada (SQLITE, [s.d.]), que executa o mesmo script DDL sem alterações. O programa também "
        "gera o arquivo 02_carga_dados.sql, com comandos INSERT em SQL padrão, que permite repetir a "
        "carga em outro sistema gerenciador de banco de dados, como o PostgreSQL.")]

S += [P("2.4 Escopo da análise", h2)]
S += [P("Conforme o enunciado da etapa, foram escolhidos a tabela fato fato_exames_cardiacos e a "
        "dimensão dim_paciente para resolver duas necessidades do gestor. A dimensão dim_clinica "
        "também é carregada, pois a tabela fato possui chave estrangeira para ela, mas não participa "
        "das análises desta etapa.")]
S += [P("2.5 Modelagem preditiva", h2)]
S += [P("Os modelos de classificação são treinados com os dados lidos do próprio Data Mart, por meio de "
        "uma junção entre a tabela fato e as duas dimensões, o que demonstra o consumo analítico da "
        "estrutura construída. A variável-alvo é o resultado do exame (positivo = 1, negativo = 0) e as "
        "variáveis preditoras são as oito demais colunas do dicionário de dados."),
      P(f"Os dados foram divididos em 80% para treinamento ({num(ml['n_treino'])} registros) e 20% para "
        f"teste ({num(ml['n_teste'])} registros), com divisão estratificada pela variável-alvo e semente "
        "aleatória fixa (random_state=42) para garantir a reprodutibilidade. As variáveis foram "
        "padronizadas com o StandardScaler, ajustado exclusivamente sobre o conjunto de treino para "
        "evitar vazamento de dados (data leakage)."),
      P("Dois classificadores supervisionados foram implementados com a biblioteca scikit-learn "
        "(PEDREGOSA et al., 2011), ambos com class_weight='balanced' para mitigar o desbalanço entre "
        "as classes: a Regressão Logística, modelo linear probabilístico usado como referência "
        "interpretável (HOSMER; LEMESHOW; STURDIVANT, 2013), e o Random Forest, modelo de conjunto "
        "de árvores de decisão capaz de capturar relações não lineares entre os exames (BREIMAN, "
        "2001). O desempenho foi avaliado por acurácia, precisão, recall e F1-Score da classe "
        "positiva, matriz de confusão, curva ROC e área sob a curva (AUC) (FAWCETT, 2006). Para "
        "verificar a estabilidade dos resultados, aplicou-se também validação cruzada estratificada "
        "de 5 partições sobre o conjunto completo, com o escalonador incluído em cada partição.")]

# ============================================================================
S += [P("3 DESENVOLVIMENTO E RESULTADOS", h1)]
S += [P("3.1 Lógica do ETL", h2)]
S += [P("Extração. O arquivo é lido com pandas com todas as colunas como texto (dtype=str) e "
        "detecção automática do delimitador. Isso evita que o pandas converta valores sem aviso e "
        "mantém toda a conversão sob controle do código. Os nomes das colunas originais são "
        "mapeados para os nomes do Data Mart (Código 1).")]
S += [P("Código 1 – Extração", legenda), codigo(trecho("bruto = pd.read_csv(", "MAPA_COLUNAS")),
      P("Fonte: 01_etl_carga.py.", fonte)]
S += [P("Transformação. As colunas numéricas são convertidas (aceitando vírgula decimal) e a variável-alvo "
        "é codificada (positive = 1, negative = 0), conforme o Código 2. Valores que não puderem "
        "ser convertidos viram nulos e são tratados na etapa seguinte.")]
S += [P("Código 2 – Conversão de tipos e codificação do alvo", legenda),
      codigo(trecho("NUMERICAS = [", "rejeitadas = []")), P("Fonte: 01_etl_carga.py.", fonte)]
S += [P("Em seguida, uma função de rejeição move para uma lista os registros que violam cada regra e os "
        "remove do fluxo (Código 3). As regras são: valores ausentes ou não numéricos (dropna), "
        "registros duplicados e as mesmas restrições CHECK do DDL (gênero em 0 ou 1, idade entre 1 e "
        "129, sinais vitais positivos e biomarcadores não negativos). Os registros rejeitados são "
        "gravados em dados/registros_rejeitados.csv, com o motivo, o que permite auditoria. Valores "
        "atípicos que não violam o domínio, como frequências cardíacas fisiologicamente implausíveis, "
        "são sinalizados e mantidos, para não distorcer a base por decisão arbitrária.")]
S += [P("Código 3 – Regras de rejeição", legenda),
      codigo(trecho("def rejeitar", "# 2.4 Valores atipicos")), P("Fonte: 01_etl_carga.py.", fonte)]
S += [P("As dimensões são formadas pelas combinações distintas dos seus atributos (por exemplo, cada par "
        "idade e gênero aparece uma única vez em dim_paciente), com chave substituta sequencial. A "
        "tabela fato recebe, para cada exame, as chaves das dimensões por meio de junções com os "
        "valores de negócio (Código 4).")]
S += [P("Código 4 – Construção das dimensões e da fato", legenda),
      codigo(trecho("# 2.6 Dimensoes", "tabelas = [")), P("Fonte: 01_etl_carga.py.", fonte)]
S += [P("Carga. O DDL é executado e as tabelas são inseridas na ordem dimensões e, por último, fato, com as "
        "chaves estrangeiras ativadas (Código 5). Assim, uma chave inexistente ou um valor fora do "
        "domínio faria a carga falhar, o que funciona como uma segunda camada de validação.")]
S += [P("Código 5 – Carga das tabelas", legenda), codigo(trecho("if DB.exists()", "def lit(v)")),
      P("Fonte: 01_etl_carga.py.", fonte)]

S += [P("3.2 Resultado da carga", h2)]
rej_linhas = [[k[0].upper() + k[1:], num(v)] for k, v in mot.items()]
t3 = ([["Linhas lidas da base original", num(N)]] +
      [["(–) Rejeitadas: " + k[0].lower() + k[1:], num(v)] for k, v in mot.items()] +
      [["<b>(=) Registros carregados em fato_exames_cardiacos</b>", f"<b>{num(V)}</b>"]])
assert N - log["rejeitadas_total"] == V
S += [P(f"A Tabela 3 reconcilia cada etapa do processo. Das {num(N)} linhas lidas, "
        f"{num(log['rejeitadas_total'])} foram rejeitadas ({num(log['duplicados_removidos'])} duplicadas), "
        f"restando {num(V)} registros carregados na tabela fato. Dos registros carregados, "
        f"{num(cl['positivos'])} são positivos e {num(cl['negativos'])} são negativos. "
        f"Foram sinalizados {num(log['atipicos_sinalizados_mantidos'])} registros com valores atípicos, "
        "mantidos na base.")]
if n_fc:
    S += [P(f"Esses registros correspondem a {num(n_fc)} exames com frequência cardíaca de "
            f"{num(fc_max)} bpm, valor fisiologicamente impossível e provavelmente um erro de "
            "digitação na origem. Eles foram mantidos porque o DDL não impõe limite superior a esse "
            "campo e porque corrigir ou excluir o dado cabe ao responsável pela base. Como a "
            "frequência cardíaca não participa das análises desta etapa, esses registros não afetam "
            "os resultados apresentados.")]
S += [bloco_tabela("Tabela 3 – Reconciliação das etapas do ETL", tabela(["Etapa", "Linhas"], t3, [12, 4], (1,)))]

S += [P("3.3 Validação da carga", h2)]
S += [P("A validação seguiu cinco verificações. A primeira é a contagem de registros por tabela "
        "(Tabela 4), que deve coincidir com o log do ETL.")]
t4 = [[a, num(b)] for a, b in val["V1_contagem_registros"]["linhas"]]
S += [bloco_tabela("Tabela 4 – Contagem de registros por tabela (V1)",
                   tabela(["Tabela", "Registros"], t4, [8, 4], (1,)))]
S += [P("Código 6 – Consulta de contagem", legenda), codigo(sql_q("V1_contagem_registros")),
      P("Fonte: 02_validacao.py.", fonte)]
S += [P(f"A tabela fato contém {num(car['fato_exames_cardiacos'])} registros, número igual ao de "
        f"registros válidos do ETL. A segunda verificação procura registros órfãos, isto é, exames "
        "cujas chaves não existem nas dimensões; o esperado é zero (Tabela 5), e o comando PRAGMA "
        "foreign_key_check também retornou vazio.")]
t5 = [[a, num(b)] for a, b in val["V2_integridade_referencial"]["linhas"]]
S += [bloco_tabela("Tabela 5 – Fatos órfãos por dimensão (V2)",
                   tabela(["Dimensão", "Fatos órfãos"], t5, [8, 4], (1,)))]
S += [P("Código 7 – Consulta de integridade referencial", legenda),
      codigo(sql_q("V2_integridade_referencial")), P("Fonte: 02_validacao.py.", fonte)]
pos, neg, tot = val["V3_distribuicao_resultado"]["linhas"][0]
S += [P(f"A terceira verificação confere a distribuição da variável-alvo na tabela fato: {num(pos)} "
        f"positivos e {num(neg)} negativos, num total de {num(tot)}, idêntica à contagem feita pelo ETL "
        "antes da carga. A quarta é uma amostra de junção entre a fato e as duas dimensões "
        "(Tabela 6), que confirma que as chaves resolvem corretamente para os valores de negócio.")]
t6 = [[str(c) if not isinstance(c, float) else dec(c, 3 if i == 8 else 2) for i, c in enumerate(r)]
      for r in val["V4_amostra_juncao"]["linhas"]]
S += [bloco_tabela("Tabela 6 – Amostra da junção fato e dimensões (V4)",
                   tabela(["id", "idade", "gên.", "FC", "PAS", "PAD", "glic.", "CK-MB", "trop.", "res."],
                          t6, [1.0, 1.4, 1.2, 1.3, 1.4, 1.4, 1.9, 1.9, 1.9, 1.3], tuple(range(10))))]
S += [P("Código 8 – Amostra de junção", legenda), codigo(sql_q("V4_amostra_juncao")),
      P("Fonte: 02_validacao.py.", fonte)]
S += [P("A quinta verificação é um teste negativo: em uma cópia do banco, tentou-se inserir dados "
        "inválidos, e as restrições do DDL rejeitaram todas as tentativas (Tabela 7). Isso comprova "
        "que a integridade é garantida pelo próprio banco, e não apenas pelo código de carga.")]
t7 = [[a, b] for a, b in val["V5_testes_restricoes"]["linhas"]]
S += [bloco_tabela("Tabela 7 – Teste de restrições do banco (V5)",
                   tabela(["Tentativa de inserção", "Resultado"], t7, [7, 9]))]

S += [P("3.4 Atendimento às necessidades do gestor", h2)]
S += [P("Necessidade 1: qual o perfil de idade e gênero dos exames positivos?", h2)]
n1 = val["N1_positividade_por_faixa_e_genero"]["linhas"]
S += [P("A consulta junta a fato à dimensão dim_paciente, agrupa por faixa etária e gênero e calcula o "
        "percentual de resultados positivos (Código 9, Tabela 8 e Figura 2). As faixas etárias são "
        "derivadas da idade na própria consulta.")]
S += [P("Código 9 – Positividade por faixa etária e gênero", legenda),
      codigo(sql_q("N1_positividade_por_faixa_e_genero")), P("Fonte: 02_validacao.py.", fonte)]
lab = lambda f: f.split(") ")[1].replace("ate", "até")
t8 = [[lab(r[0]), str(r[1]), num(r[2]), num(r[3]), dec(r[4], 1) + "%"] for r in n1]
S += [bloco_tabela("Tabela 8 – Exames e percentual de positivos por faixa etária e gênero (N1)",
                   tabela(["Faixa etária", "Gênero", "Exames", "Positivos", "% positivos"], t8,
                          [3.6, 2.6, 3.0, 3.0, 3.8], (2, 3, 4)))]
S += [bloco_figura("Figura 2 – Percentual de positivos por faixa etária e gênero",
                   RES / "grafico_positividade.png", 14.5)]
agg = {}
for f, g, ex, po, pc in n1:
    a = agg.setdefault(f, [0, 0])
    a[0] += ex
    a[1] += po
pf = [(lab(f), 100 * a[1] / a[0]) for f, a in sorted(agg.items())]
mono = all(pf[i][1] <= pf[i + 1][1] for i in range(len(pf) - 1))
alto = max(pf, key=lambda x: x[1])
baixo = min(pf, key=lambda x: x[1])
txt_tend = ("cresce a cada faixa, indo de " if mono else "varia entre as faixas, indo de ")
S += [P(f"Somando os dois gêneros, o percentual de positivos {txt_tend}{dec(baixo[1], 1)}% na faixa "
        f"\"{baixo[0]}\" a {dec(alto[1], 1)}% na faixa \"{alto[0]}\". Para o gestor, isso indica em "
        "quais faixas etárias os exames tendem a resultar mais em diagnóstico positivo, informação "
        "útil para priorizar a triagem. Como cada combinação de faixa e gênero reúne um número "
        "limitado de exames (Tabela 8), as diferenças entre gêneros devem ser lidas com cautela, e "
        "a análise descreve a base, sem estabelecer relação de causa.")]

S += [P("Necessidade 2: como os biomarcadores diferem entre exames positivos e negativos?", h2)]
n2 = val["N2_biomarcadores_por_faixa_e_resultado"]["linhas"]
S += [P("A segunda consulta usa a mesma fato e a mesma dimensão para calcular as médias de troponina, "
        "CK-MB e glicemia por faixa etária e resultado (Código 10, Tabela 9 e Figura 3).")]
S += [P("Código 10 – Biomarcadores por faixa etária e resultado", legenda),
      codigo(sql_q("N2_biomarcadores_por_faixa_e_resultado")), P("Fonte: 02_validacao.py.", fonte)]
t9 = [[lab(r[0]), "Positivo" if r[1] == 1 else "Negativo", num(r[2]), dec(r[3], 3), dec(r[4], 2),
       dec(r[5], 1)] for r in n2]
S += [bloco_tabela("Tabela 9 – Média dos biomarcadores por faixa etária e resultado (N2)",
                   tabela(["Faixa etária", "Resultado", "Exames", "Troponina", "CK-MB", "Glicemia"], t9,
                          [2.8, 2.6, 2.4, 2.8, 2.6, 2.8], (2, 3, 4, 5)))]
S += [bloco_figura("Figura 3 – Troponina média por faixa etária e resultado",
                   RES / "grafico_troponina.png", 14.5)]


def media(res, i):
    ex = sum(r[2] for r in n2 if r[1] == res)
    return sum(r[2] * r[i] for r in n2 if r[1] == res) / ex


tp, tn = media(1, 3), media(0, 3)
cp, cn = media(1, 4), media(0, 4)
gp, gn = media(1, 5), media(0, 5)
S += [P(f"Ponderando pelo número de exames, a troponina média é de {dec(tp, 3)} nos exames positivos "
        f"e de {dec(tn, 3)} nos negativos, e a CK-MB média é de {dec(cp, 2)} e {dec(cn, 2)}, "
        f"respectivamente. A glicemia média é de {dec(gp, 1)} nos positivos e {dec(gn, 1)} nos "
        "negativos. Esses valores mostram quanto cada biomarcador se separa entre os dois resultados, "
        "o que é coerente com o papel desses marcadores no diagnóstico do infarto (THYGESEN et al., "
        "2018) e fornece ao gestor uma referência para acompanhar os exames por faixa etária. As "
        "mesmas tabelas estão prontas para alimentar dashboards."),
      P(f"Uma ressalva: as médias de CK-MB são sensíveis a valores extremos. A mediana geral é de "
        f"{dec(ck_med, 2)}, enquanto o máximo é de {dec(ck_max, 2)}, e {num(ck_n50)} exames têm CK-MB "
        "acima de 50. Por isso, a média por faixa deve ser lida com cautela, e a mediana seria uma "
        "medida complementar adequada em análises futuras.")]

# ============================================================================
S += [P("3.5 Modelos preditivos", h2)]
S += [P("Os dados são lidos do Data Mart pela junção da fato com as dimensões (Código 11). Em seguida, "
        "o conjunto é dividido e os dois modelos são treinados dentro de um pipeline que inclui o "
        "escalonador (Código 12). Os modelos treinados foram salvos em arquivos .pkl na pasta modelos.")]
S += [P("Código 11 – Leitura dos dados a partir do Data Mart", legenda),
      codigo(trecho('SQL = """', "NOMES = {", arq="03_modelos_ml.py")), P("Fonte: 03_modelos_ml.py.", fonte)]
S += [P("Código 12 – Divisão dos dados e definição dos modelos", legenda),
      codigo(trecho("X_tr, X_te, y_tr", "res = {", arq="03_modelos_ml.py")), P("Fonte: 03_modelos_ml.py.", fonte)]
m = ml["modelos"]
LR, RF = "Regressão Logística", "Random Forest"
pc = lambda v: dec(100 * v, 1) + "%"
t10 = [[k, pc(v["acuracia"]), pc(v["precisao"]), pc(v["recall"]), pc(v["f1"]), dec(v["auc"], 3)]
       for k, v in m.items()]
S += [P(f"A Tabela 10 apresenta o desempenho dos modelos no conjunto de teste, que tem "
        f"{num(ml['n_teste'])} exames ({num(ml['teste_positivos'])} positivos e "
        f"{num(ml['teste_negativos'])} negativos). As métricas de precisão, recall e F1 se referem à "
        "classe positiva.")]
S += [bloco_tabela("Tabela 10 – Desempenho dos modelos no conjunto de teste",
                   tabela(["Modelo", "Acurácia", "Precisão", "Recall", "F1-Score", "AUC"], t10,
                          [4.4, 2.2, 2.2, 2.2, 2.4, 2.0], (1, 2, 3, 4, 5)))]
S += [bloco_figura("Figura 4 – Matrizes de confusão dos classificadores no conjunto de teste",
                   RES / "ml_matrizes_confusao.png", 15.0)]
melhor, outro = (RF, LR) if m[RF]["acuracia"] >= m[LR]["acuracia"] else (LR, RF)
S += [P(f"O {melhor} obteve acurácia de {pc(m[melhor]['acuracia'])} e AUC de {dec(m[melhor]['auc'], 3)}, "
        f"contra {pc(m[outro]['acuracia'])} e {dec(m[outro]['auc'], 3)} do {outro}. A diferença aparece "
        f"principalmente nos falsos negativos (Figura 4): a Regressão Logística deixou de identificar "
        f"{num(m[LR]['fn'])} dos {num(ml['teste_positivos'])} exames positivos (recall de "
        f"{pc(m[LR]['recall'])}), enquanto o Random Forest deixou de identificar {num(m[RF]['fn'])} "
        f"(recall de {pc(m[RF]['recall'])}), com {num(m[RF]['fp'])} falsos positivos. Em um contexto "
        "clínico, o falso negativo, isto é, o paciente com lesão não identificado, é o erro de maior "
        "custo, e é nele que os modelos mais se distinguem.")]
S += [bloco_figura("Figura 5 – Curvas ROC dos classificadores", RES / "ml_curva_roc.png", 10.5)]
t11 = [[k, f"{pc(v['cv_acuracia_media'])} ± {dec(100 * v['cv_acuracia_dp'], 1)}",
        f"{dec(v['cv_auc_media'], 3)} ± {dec(v['cv_auc_dp'], 3)}"] for k, v in m.items()]
S += [P("A curva ROC (Figura 5) mostra a capacidade de discriminação dos modelos em diferentes limiares "
        "de decisão: quanto mais próxima do canto superior esquerdo, melhor. A validação cruzada "
        "estratificada de 5 partições (Tabela 11) indica se esse desempenho se mantém em divisões "
        "diferentes dos dados.")]
S += [bloco_tabela("Tabela 11 – Validação cruzada estratificada de 5 partições (média ± desvio padrão)",
                   tabela(["Modelo", "Acurácia", "AUC"], t11, [6.0, 5.0, 5.0], (1, 2)))]
imp = ml["importancias"]
top2 = imp[0][1] + imp[1][1]
S += [bloco_figura("Figura 6 – Importância relativa das variáveis no Random Forest",
                   RES / "ml_importancia_variaveis.png", 14.5)]
S += [P(f"A importância das variáveis no Random Forest (Figura 6) concentra-se em {imp[0][0]} "
        f"({pc(imp[0][1])}) e {imp[1][0]} ({pc(imp[1][1])}), que somam {pc(top2)} do total. Isso é "
        "coerente com o papel desses biomarcadores no diagnóstico do infarto (THYGESEN et al., 2018), "
        "mas exige cautela na interpretação: troponina e CK-MB indicam lesão miocárdica já "
        "estabelecida, de modo que o alto desempenho reflete a identificação de um dano existente, e "
        "não a antecipação do risco a partir de sinais básicos. Além disso, o conjunto de teste é "
        "pequeno e os hiperparâmetros não foram otimizados, o que limita a generalização dos números.")]

S += [P("4 CONCLUSÃO", h1)]
S += [P(f"Este trabalho implementou o processo de ETL que alimenta o Data Mart de exames cardíacos: a "
        f"partir de {num(N)} linhas da base original, foram carregados {num(V)} exames na tabela fato "
        f"e {num(car['dim_paciente'])} e {num(car['dim_clinica'])} registros nas dimensões "
        "dim_paciente e dim_clinica, com integridade referencial comprovada por contagens, teste de "
        "registros órfãos, reconciliação com o log do ETL e teste de rejeição de dados inválidos."),
      P("Entre os desafios encontrados, destacam-se a conversão segura de tipos a partir de um arquivo "
        "de texto, a decisão sobre como tratar duplicados e valores atípicos e a necessidade de "
        "alinhar as regras de limpeza às restrições do próprio DDL. Ficou claro que decisões como "
        "rejeitar um registro, em vez de corrigi-lo, precisam ser explícitas e documentadas. A "
        "gravação dos registros rejeitados em arquivo próprio e a tabela de reconciliação tornam o "
        "processo auditável. Outro aprendizado foi o da própria modelagem: como a base não tem "
        "identificador de paciente, de data nem de local, as dimensões foram formadas por "
        "combinações distintas de atributos, e o modelo ficou restrito ao que a fonte permite."),
      P("O valor analítico da modelagem apareceu nas duas necessidades do gestor: com consultas "
        "simples sobre uma fato e uma dimensão, foi possível identificar em que faixas etárias os "
        "exames resultam mais em diagnóstico positivo e como os biomarcadores se comportam entre "
        "positivos e negativos. Os dados armazenados no Data Mart também alimentaram diretamente os "
        "modelos de classificação."),
      P(f"Na modelagem preditiva, o {melhor} superou o {outro}, com acurácia de "
        f"{pc(m[melhor]['acuracia'])} e AUC de {dec(m[melhor]['auc'], 3)} no conjunto de teste, e "
        f"manteve acurácia média de {pc(m[melhor]['cv_acuracia_media'])} na validação cruzada. A "
        f"{imp[0][0]} e a {imp[1][0]} foram as variáveis mais importantes."),
      P("Como limitações, os biomarcadores troponina e CK-MB refletem lesão miocárdica já "
        "estabelecida, e não a predição antecipada de risco; a base tem escopo único e restrito, com "
        "valores atípicos isolados; o conjunto de teste é pequeno; e não houve otimização de "
        "hiperparâmetros. Como trabalhos futuros, sugere-se treinar os modelos sem os biomarcadores de "
        "lesão, para verificar se sinais vitais e dados demográficos conseguem prever o risco de forma "
        "precoce, aplicar busca de hiperparâmetros (Grid Search ou Random Search), estender o modelo "
        "com dimensões de tempo e de local caso novas fontes as tragam e validar a arquitetura com "
        "bases clínicas externas.")]

S += [P("REFERÊNCIAS", h1c)]
refs = [
    "BREIMAN, L. Random forests. <b>Machine Learning</b>, v. 45, n. 1, p. 5-32, 2001.",
    "FAWCETT, T. An introduction to ROC analysis. <b>Pattern Recognition Letters</b>, v. 27, n. 8, "
    "p. 861-874, 2006.",
    "GÉRON, A. <b>Hands-on machine learning with Scikit-Learn, Keras, and TensorFlow</b>. 3. ed. "
    "Sebastopol: O'Reilly Media, 2022.",
    "HOSMER, D. W.; LEMESHOW, S.; STURDIVANT, R. X. <b>Applied logistic regression</b>. 3. ed. "
    "Hoboken: Wiley, 2013.",
    "INMON, W. H. <b>Building the data warehouse</b>. 4. ed. Indianapolis: Wiley, 2005.",
    "KAGGLE. <b>Heart Attack Analysis Dataset (Medicaldataset.csv)</b>. Disponível em: "
    "https://www.kaggle.com. Acesso em: 24 nov. 2026.",
    "KIMBALL, R.; ROSS, M. <b>The data warehouse toolkit</b>: the definitive guide to dimensional "
    "modeling. 3. ed. Indianapolis: Wiley, 2013.",
    "MCKINNEY, W. <b>Python para análise de dados</b>: tratamento de dados com pandas, NumPy e IPython. "
    "2. ed. São Paulo: Novatec, 2018.",
    "PEDREGOSA, F. et al. Scikit-learn: machine learning in Python. <b>Journal of Machine Learning "
    "Research</b>, v. 12, p. 2825-2830, 2011.",
    "POSTGRESQL GLOBAL DEVELOPMENT GROUP. <b>PostgreSQL Documentation</b>: CREATE TABLE. Disponível em: "
    "https://www.postgresql.org/docs/current/sql-createtable.html. Acesso em: 24 nov. 2026.",
    "SQLITE. <b>Foreign Key Support</b>. Disponível em: https://www.sqlite.org/foreignkeys.html. "
    "Acesso em: 24 nov. 2026.",
    "THYGESEN, K. et al. Fourth Universal Definition of Myocardial Infarction (2018). <b>Circulation</b>, "
    "v. 138, n. 20, p. e618-e651, 2018.",
    "WORLD HEALTH ORGANIZATION. <b>Cardiovascular diseases (CVDs)</b>. Disponível em: "
    "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds). Acesso em: 24 nov. 2026.",
]
S += [P(r, ref) for r in refs]

novo, i = [], 0
while i < len(S):
    a = S[i]
    if (isinstance(a, Paragraph) and a.style.name == "legenda" and a.getPlainText().startswith("Código")
            and i + 2 < len(S) and isinstance(S[i + 1], XPreformatted)):
        if S[i + 1].text.count("\n") <= 30:
            novo.append(KeepTogether([a, S[i + 1], S[i + 2]]))
        else:
            novo.extend([a, S[i + 1], S[i + 2]])
        i += 3
    else:
        novo.append(a)
        i += 1
doc.multiBuild(novo)
print("PDF gerado:", OUT_PDF)
