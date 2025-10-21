import streamlit as st
import pandas as pd
import io
import zipfile

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Processador de Dados", layout="wide")
st.title("Ferramenta de Ingestão e Processamento de Dados")

# --- 2. OS "CONTRATOS" DE COLUNAS ---
# Define as colunas exatas que esperamos para cada tipo de arquivo
# (Isto é crucial para a validação)

CONTRATO_PLANNING = {
    'poc_motorista': ['poc', 'motorista'],
    'motorista_veiculo': ['motorista', 'cdd', 'documento', 'telefone', 'carro'],
    'carro_placa': ['carro', 'placa', 'cdd']
}

CONTRATO_NO_PLANNING = {
    'order_motorista': ['order', 'data', 'veiculo', 'motorista'],
    'motorista_veiculo': ['motorista', 'cdd', 'documento', 'telefone', 'carro'],
    'carro_placa': ['carro', 'placa', 'cdd']
}

# --- 3. FUNÇÕES AUXILIARES (O "MOTOR") ---

def carregar_arquivos(lista_arquivos_upload):
    """Lê uma lista de arquivos (CSV ou Excel) e concatena em um único DataFrame."""
    lista_dfs = []
    if not lista_arquivos_upload: # Se a lista estiver vazia
        return None
        
    for file in lista_arquivos_upload:
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            lista_dfs.append(df)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo '{file.name}': {e}")
            return None
            
    # Concatena todos os DataFrames em um só
    df_completo = pd.concat(lista_dfs, ignore_index=True)
    return df_completo

def validar_colunas(df, colunas_esperadas):
    """Verifica se o DataFrame contém todas as colunas esperadas."""
    colunas_arquivo = df.columns
    colunas_faltando = [col for col in colunas_esperadas if col not in colunas_arquivo]
    
    if colunas_faltando:
        return False, colunas_faltando
    return True, None

# --- 4. INTERFACE DO USUÁRIO (O "SITE") ---

# O botão de seleção principal
modo = st.radio(
    "Selecione o modo de operação:",
    ("Planning", "No Planning"),
    key='modo_operacao',
    horizontal=True
)

# Dicionário para guardar os DataFrames processados
dataframes_processados = {}
validacao_passou = True
contrato_atual = None

st.divider()

if modo == "Planning":
    st.header("Modo: Planning")
    contrato_atual = CONTRATO_PLANNING
    
    # Criamos 3 colunas para os 3 uploaders
    col1, col2, col3 = st.columns(3)
    
    with col1:
        files_tipo_1 = st.file_uploader(
            "1. Arquivos de POC e Motorista",
            accept_multiple_files=True,
            key='planning_1'
        )
    with col2:
        files_tipo_2 = st.file_uploader(
            "2. Arquivos de Motorista e Veículo",
            accept_multiple_files=True,
            key='planning_2'
        )
    with col3:
        files_tipo_3 = st.file_uploader(
            "3. Arquivos de Carro e Placa",
            accept_multiple_files=True,
            key='planning_3'
        )
    
    # Mapeia os uploaders para os contratos
    uploads_info = {
        'poc_motorista': (files_tipo_1, contrato_atual['poc_motorista']),
        'motorista_veiculo': (files_tipo_2, contrato_atual['motorista_veiculo']),
        'carro_placa': (files_tipo_3, contrato_atual['carro_placa'])
    }

else: # Modo "No Planning"
    st.header("Modo: No Planning")
    contrato_atual = CONTRATO_NO_PLANNING

    col1, col2, col3 = st.columns(3)
    
    with col1:
        files_tipo_1 = st.file_uploader(
            "1. Arquivos de Ordem e Motorista",
            accept_multiple_files=True,
            key='noplanning_1'
        )
    with col2:
        files_tipo_2 = st.file_uploader(
            "2. Arquivos de Motorista e Veículo",
            accept_multiple_files=True,
            key='noplanning_2'
        )
    with col3:
        files_tipo_3 = st.file_uploader(
            "3. Arquivos de Carro e Placa",
            accept_multiple_files=True,
            key='noplanning_3'
        )

    # Mapeia os uploaders para os contratos
    uploads_info = {
        'order_motorista': (files_tipo_1, contrato_atual['order_motorista']),
        'motorista_veiculo': (files_tipo_2, contrato_atual['motorista_veiculo']),
        'carro_placa': (files_tipo_3, contrato_atual['carro_placa'])
    }

st.divider()

# Verifica se todos os 3 uploaders têm pelo menos um arquivo
todos_uploads_prontos = all(len(info[0]) > 0 for info in uploads_info.values())

if not todos_uploads_prontos:
    st.info("Por favor, faça o upload de pelo menos um arquivo em cada uma das 3 seções acima para continuar.")
else:
    # Se todos os uploads estiverem prontos, mostra o botão de processar
    if st.button("Processar e Gerar Arquivos", type="primary", use_container_width=True):
        
        with st.spinner("Lendo, validando e processando arquivos..."):
            
            # Itera sobre cada TIPO de upload
            for nome_tipo, (lista_arquivos, colunas_esperadas) in uploads_info.items():
                
                # 1. Carrega e Concatena
                df_completo = carregar_arquivos(lista_arquivos)
                if df_completo is None:
                    st.error(f"Erro ao carregar arquivos para '{nome_tipo}'.")
                    validacao_passou = False
                    continue # Pula para o próximo tipo
                
                # 2. Valida
                is_valid, colunas_faltando = validar_colunas(df_completo, colunas_esperadas)
                if not is_valid:
                    st.error(f"Validação falhou para '{nome_tipo}'. Colunas faltando: {colunas_faltando}")
                    validacao_passou = False
                    continue # Pula para o próximo tipo
                
                # 3. Limpa (remove duplicadas) e armazena
                df_limpo = df_completo[colunas_esperadas].drop_duplicates()
                dataframes_processados[nome_tipo] = df_limpo
                
                st.write(f"✔️ Arquivos de '{nome_tipo}' lidos e validados ({len(df_limpo)} linhas únicas).")

            # --- GERAÇÃO DO ZIP DE SAÍDA ---
            if validacao_passou:
                st.success("Todos os arquivos foram processados com sucesso!")

                try:
                    memory_zip = io.BytesIO()
                    with zipfile.ZipFile(memory_zip, 'w') as zf:
                        
                        # Escreve os DataFrames processados no ZIP
                        for nome_tipo, df in dataframes_processados.items():
                            zf.writestr(f"{nome_tipo}_consolidado.csv", df.to_csv(index=False))
                    
                    memory_zip.seek(0)
                    
                    st.download_button(
                        label="Baixar CSVs Processados (ZIP)",
                        data=memory_zip,
                        file_name=f"arquivos_{modo.lower()}_processados.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar o arquivo ZIP: {e}")
            else:
                st.error("Processamento falhou. Corrija os arquivos com erro e tente novamente.")
