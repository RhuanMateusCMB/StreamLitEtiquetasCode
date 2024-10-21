import streamlit as st
import pdfplumber
import re
import os
import shutil
from reportlab.pdfgen import canvas
import PyPDF2
import pandas as pd

# Função para remover espaços e caracteres especiais
def formatarReferencia(texto):
    return re.sub(r'\s+|[^a-zA-Z0-9]', '', texto).upper()

st.set_page_config(
    layout="wide", 
    page_title="CMB Etiquetas",
    page_icon= "logo.ico")

data_fabricacao = st.date_input(label="Data de Fabricaçao dos Produtos:", format="DD/MM/YYYY")

itens_pedido = []
cliente = None

# Função para extrair o cliente do PDF
def extrair_cliente(conteudo_pdf):
    global cliente
    for linha in conteudo_pdf.split('\n'):
        if 'Cliente:' in linha:
            cliente = linha.split(':')[1].strip()
            return cliente
    return None

# Função para extrair itens do pedido a partir do PDF
def extrair_itens_pedido(conteudo_pdf):

    produtos_lista = []
    
    # Carrega a planilha de produtos
    url = "https://docs.google.com/spreadsheets/d/10xH-WrGzH3efBqlrrUvX4kHotmL-sX19RN3_dn5YqyA/gviz/tq?tqx=out:csv"
    df_excel = pd.read_csv(url)

    for _, row in df_excel.iterrows():
        if pd.isna(row['ID']):
            continue
        
        # Extrair código e nome do produto
        codigo_produto = str(int(row['ID']))
        nome_produto = str(row['Produto']).upper()
        referencia = f"{codigo_produto} - {nome_produto}"

        # Comparar produto e ID no PDF
        if formatarReferencia(referencia) in formatarReferencia(conteudo_pdf):
            quantidade = 1
        else:
            quantidade = 0  # Não encontrado

        produtos_lista.append({'produto': nome_produto, 'quantidade': quantidade})
    
    return produtos_lista

# Interface para upload de arquivo
arquivo_pedido = st.file_uploader(label="Arraste ou Selecione o Arquivo em PDF do Pedido:", type=['pdf'])

if arquivo_pedido is not None:
    with pdfplumber.open(arquivo_pedido) as pdf:
        conteudo_pdf = ''
        for pagina in pdf.pages:
            conteudo_pdf += pagina.extract_text()

    cliente = extrair_cliente(conteudo_pdf)
    itens_pedido = extrair_itens_pedido(conteudo_pdf)
    
    st.write(f"Cliente: {cliente}")
    st.write("Produtos extraídos:")
    st.write(itens_pedido)

    # Checa se há itens para gerar etiquetas
    if any(item['quantidade'] > 0 for item in itens_pedido):
        st.success("Produtos encontrados. Pronto para gerar etiquetas.")

        # (Código para gerar PDF de etiquetas continua...)
    else:
        st.warning("Nenhum produto encontrado no pedido.")
