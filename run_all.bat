@echo off
setlocal
if not exist dados\Medicaldataset.csv (
  echo ERRO: coloque o Medicaldataset.csv na pasta dados\ e execute novamente.
  exit /b 1
)
echo [1/4] Executando ETL e carga do Data Mart...
python 01_etl_carga.py || goto :erro
echo [2/4] Validando a carga e executando as consultas do gestor...
python 02_validacao.py || goto :erro
echo [3/4] Treinando e avaliando os modelos de classificacao...
python 03_modelos_ml.py || goto :erro
echo [4/4] Gerando o relatorio PDF...
python 04_gerar_relatorio.py || goto :erro
echo.
echo Concluido. PDF: Relatorio_Final_DataMart_Cardiaco.pdf
exit /b 0
:erro
echo.
echo Falha na etapa acima. Verifique a mensagem de erro.
exit /b 1
