import streamlit as st
import pdfplumber
import math
import re
import io
import os
import shutil
from streamlit_gsheets import GSheetsConnection
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import PyPDF2
import pandas as pd

def formatarReferencia(texto):
    return re.sub(r'\s+|[^a-zA-Z0-9]', '', texto).upper()

st.set_page_config(
    layout="wide", 
    page_title="CMB Etiquetas",
    page_icon= "logo.ico")

data_fabricacao = st.date_input(label="Data de Fabricaçao dos Produtos:", format="DD/MM/YYYY")

itens_pedido = []
cliente = None

def extrair_cliente(conteudo_pdf):
    global cliente
    for linha in conteudo_pdf.split('\n'):
        if 'Cliente:' in linha:
            cliente = linha.split(':')[1].strip()
            return cliente
    return None

def extrair_itens_pedido(conteudo_pdf):

    produtos_lista = []

    url = "https://docs.google.com/spreadsheets/d/10xH-WrGzH3efBqlrrUvX4kHotmL-sX19RN3_dn5YqyA/gviz/tq?tqx=out:csv"
    df_excel = pd.read_csv(url)
            
    for _, row in df_excel.iterrows():
        if pd.isna(row['ID']):
            continue

        codigo_produto = str(int(row['ID']))
        nome_produto = str(row['Produto']).upper()
        referencia = f"{codigo_produto} - {nome_produto}"

        if formatarReferencia(referencia) in formatarReferencia(conteudo_pdf):
            quantidade = 1 
        else:
            quantidade = 0  

        produtos_lista.append({'produto': nome_produto, 'quantidade': quantidade})
    return produtos_lista


# Interface
url = "https://docs.google.com/spreadsheets/d/10xH-WrGzH3efBqlrrUvX4kHotmL-sX19RN3_dn5YqyA/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

with st.sidebar:
    st.header("GERADOR DE ETIQUETAS CMB")
    arquivo_pedido = st.file_uploader(label="Arraste ou Selecione o Arquivo em PDF do Pedido:", type=['pdf'])
    
    st.markdown("[Base de Dados](https://docs.google.com/spreadsheets/d/10xH-WrGzH3efBqlrrUvX4kHotmL-sX19RN3_dn5YqyA/edit?usp=sharing)", unsafe_allow_html=True)

if arquivo_pedido:
    data_fabricacao = data_fabricacao.strftime("%d/%m/%Y")
    st.success(f"Data de Fabricaçao dos Produtos: :blue[{data_fabricacao}]")
    arquivo_pedido_bytes = io.BytesIO(arquivo_pedido.read())
    with pdfplumber.open(arquivo_pedido_bytes) as pdf:
        conteudo_pdf = ""
        for pagina in pdf.pages:
            conteudo_pdf += pagina.extract_text()

        cliente = extrair_cliente(conteudo_pdf)
        if cliente:
            st.success(f"Cliente identificado: {cliente}")
        else:
            st.error("Nenhum cliente identificado no PDF.")

        # Carregar base de dados dos produtos e extrair itens do pedido
        df_excel = conn.read(spreadsheet=url)
        pacote_dict = dict(zip(df_excel["Produto"], df_excel["ProdutoPacote"]))
        itens_pedido = extrair_itens_pedido(conteudo_pdf)

        # Diretório para salvar os PDFs
        pasta_destino = "pedidos"

        # Criar o diretório se não existir
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino)
        else:
            # Limpar a pasta "pedidos" se já existir
            shutil.rmtree(pasta_destino)
            os.makedirs(pasta_destino)

        # Tamanho da página em pontos (9.8cm de largura x 2.5cm de altura)
        if itens_pedido:
            # Gerar PDFs para cada item do pedido
            for idx, item in enumerate(itens_pedido):
                produto = item["produto"]
                quantidade = item["quantidade"]

                for i in range(quantidade):
                    fileName = f"{idx+1:03d}_{cliente}_{produto}_{i+1:03d}.pdf".replace('/', '-').replace(' ', '_')
                    documentTitle = cliente
                    title = produto
                    subTitle = 'etiquetas'
                    caminho_completo = os.path.join(pasta_destino, fileName)
                    
                    pdf = canvas.Canvas(caminho_completo)
                    page_width = 9.8 / 2.54 * inch  # Convertendo cm para polegadas e depois para pontos
                    page_height = 2.5 / 2.54 * inch  # Convertendo cm para polegadas e depois para pontos
                    pdf.setPageSize((page_width, page_height))
                    pdf.setTitle(documentTitle)
                    pdf.setTitle(title)

                    # Verificar se o produto existe no DataFrame
                    if produto in df_excel["Produto"].values:
                        descricao_produto = df_excel[df_excel["Produto"] == produto]["Descricao"].values[0]
                    else:
                        # Usar o nome do produto como descrição padrão
                        descricao_produto = produto

                    regex = r"(?m)^(.*?)(?::|\.)\s*(.*?)(?::|\.)\s*(.*?)$"

                    match = re.search(regex, descricao_produto)
                    if match:
                        ingredientes = match.group(1).strip()
                        descricao = match.group(2).strip()
                        validade = match.group(3).strip()
                    else:
                        ingredientes = descricao_produto
                        descricao = ""
                        validade = ""

                    if not any(char.isdigit() for char in validade):
                        validade = 'Consumo Diário.'

                    if descricao == "Informações na Embalagem" or descricao == "":
                        pdf.setFont("Helvetica-Bold", 10)
                        pdf.drawCentredString(page_width / 2, page_height - 20, title)
                        
                        # Ajustando o texto da validade e data de fabricação
                        pdf.setFont("Helvetica", 7)
                        pdf.drawString(30, 15, f"{validade}")
                        pdf.setFont("Helvetica-Bold", 7)
                        pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
                        pdf.setFont("Helvetica", 7)
                        pdf.drawCentredString(140, 5, "Fabricado por Baxter Indústria de Alimentos Ltda CNPJ: 00.558.662/000-81")

                    else:
                        # Dividir a descrição em partes para o PDF
                        parte1 = descricao[:90].strip()
                        parte2 = descricao[90:].strip()

                        pdf.setFont("Helvetica-Bold", 10)
                        pdf.drawCentredString(140, 60, title)
                        # Desenhar as partes do texto no PDF
                        pdf.setFont("Helvetica", 7)
                        pdf.drawCentredString(140, 50, f"{ingredientes}:")

                        pdf.setFont("Helvetica", 6)
                        pdf.drawCentredString(page_width / 2, page_height - 30, parte1)
                        pdf.drawCentredString(page_width / 2, page_height - 40, parte2)

                        # Ajustando o texto da validade e data de fabricação
                        pdf.setFont("Helvetica", 7)
                        pdf.drawString(30, 15, f"{validade}")
                        pdf.setFont("Helvetica-Bold", 7)
                        pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
                        pdf.setFont("Helvetica", 7)
                        pdf.drawCentredString(140, 5, "Fabricado por: Baxter Indústria de Alimentos LTDA CNPJ: 00.558.662/000-81")
                    pdf.save()
        merger = PyPDF2.PdfMerger()

        # Ordenar a lista de arquivos antes de combinar
        lista_arquivos = sorted(os.listdir(pasta_destino))
        for arquivo in lista_arquivos:
            if ".pdf" in arquivo:
                caminho_arquivo = os.path.join(pasta_destino, arquivo)
                if os.path.isfile(caminho_arquivo):  # Verifica se é um arquivo válido
                    merger.append(caminho_arquivo)

        # Diretório para salvar o PDF combinado
        pasta_destino_combinados = "pedidos_combinados"

        # Criar o diretório se não existir
        if not os.path.exists(pasta_destino_combinados):
            os.makedirs(pasta_destino_combinados)

        # Definir o caminho completo para o arquivo PDF combinado
        arquivo_combinado = os.path.join(pasta_destino_combinados, f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_'))

        # Escrever o PDF combinado em um novo arquivo
        merger.write(arquivo_combinado)
        merger.close()

        # Fornecer o download do PDF combinado
        with open(arquivo_combinado, "rb") as pdf_file:
            PDFbyte = pdf_file.read()

            # Fazer o download do arquivo
        # Fornecer o download do PDF combinado, se houver etiquetas geradas
        if lista_arquivos:
            st.success("Etiquetas geradas com sucesso!")
            # Fazer o download do arquivo
            if st.button(label="Preparar o Download"):
                if os.path.exists(arquivo_combinado):  # Verifica se o arquivo combinado existe
                    with open(arquivo_combinado, "rb") as file:
                        bytes = file.read()
                        st.download_button(label="Clique aqui para baixar o PDF gerado", data=bytes, file_name=f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_'))
        else:
            st.warning("Nenhuma etiqueta gerada para impressão.")
            
        st.text("")
        st.text("")

    # Adicionar botão para apagar as pastas após o processo
    if st.button("Finalizar Processos"):
        shutil.rmtree(pasta_destino)
        shutil.rmtree(pasta_destino_combinados)
        st.success("Processos Finalizados com Sucesso!")

st.write("##")
st.write("Desenvolvido por CMB Capital")
st.write("© 2024 CMB Capital. Todos os direitos reservados.")
