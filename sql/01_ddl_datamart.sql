-- =====================================================================
-- Data Mart: Exames Cardiacos (Esquema Estrela / Star Schema)
-- Projeto: IA e Machine Learning para identificacao de risco cardiovascular
-- Base de origem: Medicaldataset.csv (Kaggle) - 1.319 registros
-- (Script da Entrega Parcial 1 - Anexo A)
-- =====================================================================

-- Remocao das tabelas (ordem inversa das dependencias), para permitir reexecucao
DROP TABLE IF EXISTS fato_exames_cardiacos;
DROP TABLE IF EXISTS dim_clinica;
DROP TABLE IF EXISTS dim_paciente;

-- ---------------------------------------------------------------------
-- DIMENSAO PACIENTE: contexto demografico
-- ---------------------------------------------------------------------
CREATE TABLE dim_paciente (
    id_paciente INTEGER      NOT NULL,
    idade       SMALLINT     NOT NULL,
    genero      SMALLINT     NOT NULL,
    CONSTRAINT pk_dim_paciente PRIMARY KEY (id_paciente),
    CONSTRAINT ck_paciente_idade CHECK (idade > 0 AND idade < 130),
    CONSTRAINT ck_paciente_genero CHECK (genero IN (0, 1))
);

-- ---------------------------------------------------------------------
-- DIMENSAO CLINICA: contexto fisiologico do atendimento
-- ---------------------------------------------------------------------
CREATE TABLE dim_clinica (
    id_clinica          INTEGER  NOT NULL,
    frequencia_cardiaca SMALLINT NOT NULL,
    pressao_sistolica   SMALLINT NOT NULL,
    pressao_diastolica  SMALLINT NOT NULL,
    CONSTRAINT pk_dim_clinica PRIMARY KEY (id_clinica),
    CONSTRAINT ck_clinica_fc  CHECK (frequencia_cardiaca > 0),
    CONSTRAINT ck_clinica_pas CHECK (pressao_sistolica > 0),
    CONSTRAINT ck_clinica_pad CHECK (pressao_diastolica > 0)
);

-- ---------------------------------------------------------------------
-- TABELA FATO: metricas quantitativas dos exames e chaves estrangeiras
-- Granularidade: um registro por exame cardiaco realizado
-- ---------------------------------------------------------------------
CREATE TABLE fato_exames_cardiacos (
    id_exame    INTEGER      NOT NULL,
    id_paciente INTEGER      NOT NULL,
    id_clinica  INTEGER      NOT NULL,
    glicemia    NUMERIC(8,2) NOT NULL,
    ck_mb       NUMERIC(8,3) NOT NULL,
    troponina   NUMERIC(8,4) NOT NULL,
    resultado   SMALLINT     NOT NULL,
    CONSTRAINT pk_fato_exames PRIMARY KEY (id_exame),
    CONSTRAINT fk_fato_paciente FOREIGN KEY (id_paciente)
        REFERENCES dim_paciente (id_paciente),
    CONSTRAINT fk_fato_clinica FOREIGN KEY (id_clinica)
        REFERENCES dim_clinica (id_clinica),
    CONSTRAINT ck_fato_resultado CHECK (resultado IN (0, 1))
);

-- Indices nas chaves estrangeiras para acelerar as juncoes analiticas
CREATE INDEX idx_fato_paciente ON fato_exames_cardiacos (id_paciente);
CREATE INDEX idx_fato_clinica ON fato_exames_cardiacos (id_clinica);
