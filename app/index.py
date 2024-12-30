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
import time

st.set_page_config(
    layout="wide", 
    page_title="CMB Etiquetas",
    page_icon="logo.ico"
)

data_fabricacao = st.date_input(label="Data de Fabricação dos Produtos:", format="DD/MM/YYYY")

itens_pedido = []
cliente = None

def extrair_cliente(conteudo_pdf):
    global cliente
    for linha in conteudo_pdf.split('\n'):
        if 'Cliente:' in linha:
            cliente = linha.split(':')[1].strip()
            return cliente
    return None

def extrair_itens_pedido(conteudo_pdf, pacote_dict):
    itens_pedido = []
    produtos_especiais = {
        '2969': 'MINI CROISSANT COM TOMATE E SALAME',
        '3472': 'MINI FOLHADO BAUNILHA E CANELA 25G',
        '48': 'TORRADA AMANT C/CEBOLA E OREGANO'
    }
    
    padrao_completo = r'(\d+)\s+(.*?)\s+(\d+,?\d*(?:\s*[gG])?)\s*(UN|UND|KG|kg|Kg|G|g|Un|Und|un|und)?\s+R\$\s*\d+,\d+\s+-----\s+R\$\s*\d+,\d+'
    padrao_sem_nome = r'(\d+)\s+(\d+,?\d*)\s*(UN|UND|KG|kg|Kg|G|g|Un|Und|un|und)\s+R\$\s*\d+,\d+\s+-----\s+R\$\s*\d+,\d+'
    
    for linha in conteudo_pdf.split('\n'):
        try:
            if any(char.isdigit() for char in linha):
                match_completo = re.search(padrao_completo, linha)
                match_sem_nome = re.search(padrao_sem_nome, linha)
                
                if match_completo:
                    id_produto = str(int(match_completo.group(1)))
                    nome_produto = match_completo.group(2).strip()
                    quantidade_str = match_completo.group(3)
                    unidade = match_completo.group(4).upper()
                elif match_sem_nome:
                    id_produto = str(int(match_sem_nome.group(1)))
                    quantidade_str = match_sem_nome.group(2)
                    unidade = match_sem_nome.group(3).upper()
                    nome_produto = produtos_especiais.get(id_produto, f"Produto {id_produto}")
                else:
                    continue
                
                if unidade in ['UND', 'UN', 'U', 'Un', 'und', 'Und', 'un']:
                    unidade = 'UN'
                elif unidade in ['KG', 'Kg', 'kg']:
                    unidade = 'KG'
                elif unidade in ['G', 'g']:
                    unidade = 'G'
                
                quantidade_produto = float(quantidade_str.replace(',', '.'))
                
                if id_produto in pacote_dict:
                    valor_pacote = pacote_dict[id_produto]
                    if valor_pacote == 0:
                        etiquetas_necessarias = 0
                    elif unidade == 'KG':
                        quantidade_gramas = quantidade_produto * 1000
                        valor_pacote_gramas = valor_pacote * 1000
                        etiquetas_necessarias = math.ceil(quantidade_gramas / valor_pacote_gramas)
                    else:
                        etiquetas_necessarias = math.ceil(quantidade_produto / valor_pacote)
                    
                    item = {
                        'number': id_produto,
                        'id_produto': id_produto,
                        'nome_produto': nome_produto,
                        'quantidade_produto': quantidade_produto,
                        'unidade': unidade,
                        'etiquetas_necessarias': etiquetas_necessarias
                    }
                    itens_pedido.append(item)
                else:
                    st.warning(f"\nAVISO: Produto não encontrado na base de dados: {id_produto} - {nome_produto}")
        except Exception as e:
            st.error(f"Erro ao processar item do pedido")
    
    return itens_pedido

def carregar_dados_produtos(df_excel):
    df_excel['ID'] = df_excel['ID'].astype(str)
    return dict(zip(df_excel["ID"], df_excel["ProdutoPacote"]))

# Interface
url = ""

conn = st.connection("gsheets", type=GSheetsConnection)

with st.sidebar:
    st.header("GERADOR DE ETIQUETAS CMB")
    arquivo_pedido = st.file_uploader(label="Arraste ou Selecione o Arquivo em PDF do Pedido:", type=['pdf'])
    st.markdown("[Base de Dados](https://docs.google.com/spreadsheets/d/10xH-WrGzH3efBqlrrUvX4kHotmL-sX19RN3_dn5YqyA/edit?usp=sharing)", unsafe_allow_html=True)

if arquivo_pedido:
    data_fabricacao = data_fabricacao.strftime("%d/%m/%Y")
    st.success(f"Data de Fabricação dos Produtos: :blue[{data_fabricacao}]")
    
    try:
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

            df_excel = conn.read(spreadsheet=url)
            pacote_dict = carregar_dados_produtos(df_excel)
            itens_pedido = extrair_itens_pedido(conteudo_pdf, pacote_dict)

            pasta_destino = "pedidos"
            if not os.path.exists(pasta_destino):
                os.makedirs(pasta_destino)
            else:
                shutil.rmtree(pasta_destino)
                os.makedirs(pasta_destino)

            if itens_pedido:
                total_etiquetas = sum(item["etiquetas_necessarias"] for item in itens_pedido)
                etiquetas_geradas = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()

                page_width = 9.8 / 2.54 * inch
                page_height = 2.5 / 2.54 * inch

                for idx, item in enumerate(itens_pedido):
                    produto = item["nome_produto"]
                    quantidade = item["etiquetas_necessarias"]

                    for i in range(quantidade):
                        try:
                            etiquetas_geradas += 1
                            progress = int((etiquetas_geradas / total_etiquetas) * 100)
                            progress_bar.progress(progress)
                            status_text.text(f"Gerando etiqueta {etiquetas_geradas} de {total_etiquetas}")
                            
                            fileName = f"{idx+1:03d}_{cliente}_{produto}_{i+1:03d}.pdf".replace('/', '-').replace(' ', '_')
                            documentTitle = cliente
                            title = produto
                            caminho_completo = os.path.join(pasta_destino, fileName)
                            
                            pdf = canvas.Canvas(caminho_completo)
                            pdf.setPageSize((page_width, page_height))
                            pdf.setTitle(documentTitle)

                            produto_info = df_excel[df_excel["ID"].astype(str) == item["id_produto"]]
                            if not produto_info.empty:
                                descricao_produto = produto_info["Descricao"].values[0]
                            else:
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
                                
                                pdf.setFont("Helvetica", 7)
                                pdf.drawString(30, 15, f"{validade}")
                                pdf.setFont("Helvetica-Bold", 7)
                                pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
                                pdf.setFont("Helvetica", 7)
                                pdf.drawCentredString(140, 5, "Fabricado por Baxter Indústria de Alimentos Ltda CNPJ: 00.558.662/000-81")
                            else:
                                parte1 = descricao[:90].strip()
                                parte2 = descricao[90:].strip()

                                pdf.setFont("Helvetica-Bold", 10)
                                pdf.drawCentredString(140, 60, title)
                                pdf.setFont("Helvetica", 7)
                                pdf.drawCentredString(140, 50, f"{ingredientes}:")

                                pdf.setFont("Helvetica", 6)
                                pdf.drawCentredString(page_width / 2, page_height - 30, parte1)
                                pdf.drawCentredString(page_width / 2, page_height - 40, parte2)

                                pdf.setFont("Helvetica", 7)
                                pdf.drawString(30, 15, f"{validade}")
                                pdf.setFont("Helvetica-Bold", 7)
                                pdf.drawString(page_width - 80, 15, f"Fab.: {data_fabricacao}")
                                pdf.setFont("Helvetica", 7)
                                pdf.drawCentredString(140, 5, "Fabricado por: Baxter Indústria de Alimentos LTDA CNPJ: 00.558.662/000-81")
                            pdf.save()
                        except Exception as e:
                            st.error(f"Erro ao gerar etiqueta")

                merger = PyPDF2.PdfMerger()
                pasta_destino_combinados = "pedidos_combinados"

                if not os.path.exists(pasta_destino_combinados):
                    os.makedirs(pasta_destino_combinados)

                lista_arquivos = sorted(os.listdir(pasta_destino))
                for arquivo in lista_arquivos:
                    if arquivo.endswith(".pdf"):
                        caminho_arquivo = os.path.join(pasta_destino, arquivo)
                        if os.path.isfile(caminho_arquivo):
                            merger.append(caminho_arquivo)

                arquivo_combinado = os.path.join(pasta_destino_combinados, f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_'))
                merger.write(arquivo_combinado)
                merger.close()

                if lista_arquivos:
                    st.success("Etiquetas geradas com sucesso!")
                    if st.button(label="Preparar o Download"):
                        if os.path.exists(arquivo_combinado):
                            with open(arquivo_combinado, "rb") as file:
                                bytes = file.read()
                                st.download_button(
                                    label="Clique aqui para baixar o PDF gerado", 
                                    data=bytes, 
                                    file_name=f"{cliente}_etiquetas.pdf".replace('/', '-').replace(' ', '_')
                                )
                else:
                    st.warning("Nenhuma etiqueta gerada para impressão.")
                
            st.text("")
            st.text("")

    except Exception as e:
        st.error("Ocorreu um erro durante o processamento do arquivo. Por favor, tente novamente.")

    if st.button("Finalizar Processos"):
        try:
            if os.path.exists(pasta_destino):
                shutil.rmtree(pasta_destino)
            if os.path.exists(pasta_destino_combinados):
                shutil.rmtree(pasta_destino_combinados)
            st.success("Processos Finalizados com Sucesso!")
        except Exception as e:
            st.error("Erro ao finalizar processos. Por favor, tente novamente.")

st.write("##")
st.write("Desenvolvido por CMB Capital")
st.write("© 2024 CMB Capital. Todos os direitos reservados.")
