-- Consultas de validacao e das necessidades do gestor (SQL padrao)

-- V1_contagem_registros
SELECT 'dim_paciente' AS tabela, COUNT(*) AS registros FROM dim_paciente UNION ALL SELECT 'dim_clinica', COUNT(*) FROM dim_clinica UNION ALL SELECT 'fato_exames_cardiacos', COUNT(*) FROM fato_exames_cardiacos;

-- V2_integridade_referencial
SELECT 'dim_paciente' AS dimensao, COUNT(*) AS fatos_orfaos FROM fato_exames_cardiacos f LEFT JOIN dim_paciente d ON f.id_paciente = d.id_paciente WHERE d.id_paciente IS NULL UNION ALL SELECT 'dim_clinica', COUNT(*) FROM fato_exames_cardiacos f LEFT JOIN dim_clinica d ON f.id_clinica = d.id_clinica WHERE d.id_clinica IS NULL;

-- V3_distribuicao_resultado
SELECT SUM(CASE WHEN resultado = 1 THEN 1 ELSE 0 END) AS positivos, SUM(CASE WHEN resultado = 0 THEN 1 ELSE 0 END) AS negativos, COUNT(*) AS total FROM fato_exames_cardiacos;

-- V4_amostra_juncao
SELECT f.id_exame, p.idade, p.genero, c.frequencia_cardiaca, c.pressao_sistolica, c.pressao_diastolica, f.glicemia, f.ck_mb, f.troponina, f.resultado FROM fato_exames_cardiacos f JOIN dim_paciente p ON f.id_paciente = p.id_paciente JOIN dim_clinica c ON f.id_clinica = c.id_clinica ORDER BY f.id_exame LIMIT 5;

-- N1_positividade_por_faixa_e_genero
SELECT CASE WHEN p.idade < 40 THEN '1) ate 39' WHEN p.idade < 50 THEN '2) 40-49' WHEN p.idade < 60 THEN '3) 50-59' WHEN p.idade < 70 THEN '4) 60-69' ELSE '5) 70+' END AS faixa_etaria, p.genero, COUNT(*) AS exames, SUM(f.resultado) AS positivos, ROUND(100.0 * SUM(f.resultado) / COUNT(*), 1) AS pct_positivos FROM fato_exames_cardiacos f JOIN dim_paciente p ON f.id_paciente = p.id_paciente GROUP BY faixa_etaria, p.genero ORDER BY faixa_etaria, p.genero;

-- N2_biomarcadores_por_faixa_e_resultado
SELECT CASE WHEN p.idade < 40 THEN '1) ate 39' WHEN p.idade < 50 THEN '2) 40-49' WHEN p.idade < 60 THEN '3) 50-59' WHEN p.idade < 70 THEN '4) 60-69' ELSE '5) 70+' END AS faixa_etaria, f.resultado, COUNT(*) AS exames, ROUND(AVG(f.troponina), 3) AS troponina_media, ROUND(AVG(f.ck_mb), 2) AS ck_mb_media, ROUND(AVG(f.glicemia), 1) AS glicemia_media FROM fato_exames_cardiacos f JOIN dim_paciente p ON f.id_paciente = p.id_paciente GROUP BY faixa_etaria, f.resultado ORDER BY faixa_etaria, f.resultado;