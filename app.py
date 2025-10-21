import streamlit as st
import pandas as pd
import io
import zipfile

# --- 1. CONFIGURAÇÃO DA PÁGINA E DOS "CONTRATOS" ---
st.set_page_config(page_title="Processador de Dados", layout="wide")
st.title("Ferramenta de Extração e Geração de CSVs")

# --- CONTRATOS 100% EM MINÚSCULAS ---
# O sistema irá procurar por estes nomes (ignora maiúsculas/minúsculas)
CONTRATO_PLANNING = {
    'depara': ['pvd_id', 'driver_id'],
    'driver': ['driver_id', 'vehicle_id', 'document', 'dc_id', 'display_id', 'name', 'phone', 'active', 'logistic_operator_id'],
    'vehicle': ['vehicle_id', 'plate', 'dc_id', 'display_id', 'type', 'state', 'active', 'logistic_operator_id']
}

CONTRATO_NO_PLANNING = {
    'tour': ['pvd_id', 'dc_id', 'vehicle_id', 'driver_id', 'date', 'order_id', 'tour_id', 'display_id', 'trip_external_id', 'trip_display_id', 'trip_expected_start_timestamp'],
    'driver': ['driver_id', 'vehicle_id', 'document', 'dc_id', 'display_id', 'name', 'phone', 'active', 'logistic_operator_id'],
    'vehicle': ['vehicle_id', 'plate', 'dc_id', 'display_id', 'type', 'state', 'active', 'logistic_operator_id']
}


# --- 2. INTERFACE - INSTRUÇÕES E SELEÇÃO DE MODO ---

with st.expander("Clique aqui para ver as colunas necessárias em seus arquivos de upload"):
    st.info("O sistema não diferencia maiúsculas/minúsculas (ex: 'PVD_id' e 'pvd_id' são iguais). Seu(s) arquivo(s) devem conter colunas com estes nomes:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Modo Planning")
        for nome_csv, colunas in CONTRATO_PLANNING.items():
            st.code(f"{nome_csv}: {colunas}")
    with col2:
        st.subheader("Modo No Planning")
        for nome_csv, colunas in CONTRATO_NO_PLANNING.items():
            st.code(f"{nome_csv}: {colunas}")

modo = st.radio(
    "1. Selecione o modo de operação:",
    ("Planning", "No Planning"),
    key='modo_operacao',
    horizontal=True
)

st.divider()

# --- 3. INTERFACE - UPLOAD ---

st.subheader("2. Faça o upload dos seus arquivos de dados")
st.write("Você pode enviar um ou mais arquivos (Excel ou CSV). O sistema irá juntar e extrair as informações necessárias.")

uploaded_files = st.file_uploader(
    "Arraste e solte ou clique para selecionar os arquivos",
    accept_multiple_files=True,
    key='file_uploader',
    type=['csv', 'xlsx'] # Especifica os tipos aceitos
)

st.divider()

# --- 4. LÓGICA DE PROCESSAMENTO (COM PADRONIZAÇÃO DE COLUNAS) ---

def carregar_e_concatenar(lista_arquivos):
    """Lê uma lista de arquivos, padroniza colunas e junta em um DataFrame."""
    if not lista_arquivos:
        return None
    
    lista_dfs = []
    for file in lista_arquivos:
        df = None
        try:
            file_name = file.name
            
            if file_name.endswith('.xlsx'):
                df = pd.read_excel(file)
            elif file_name.endswith('.csv'):
                file.seek(0)
                df = pd.read_csv(file)
                # Auto-detecta delimitador ; se o padrão (,) falhar
                if df.shape[1] == 1:
                    file.seek(0)
                    df = pd.read_csv(file, sep=';')
            
            if df is not None:
                # Padroniza todas as colunas: minúsculas e sem espaços
                df.columns = df.columns.str.lower().str.strip()
                lista_dfs.append(df)
            else:
                st.error(f"Não foi possível processar o arquivo '{file_name}'.")
                return None
        except Exception as e:
            st.error(f"Não foi possível ler o arquivo '{file_name}'. Verifique o formato. Erro: {e}")
            return None
    
    if not lista_dfs:
        return None
        
    df_completo = pd.concat(lista_dfs, ignore_index=True)
    return df_completo

if uploaded_files:
    if st.button("Processar e Gerar CSVs", type="primary", use_container_width=True):
        
        with st.spinner("Lendo e consolidando seus arquivos..."):
            df_consolidado = carregar_e_concatenar(uploaded_files)

        if df_consolidado is not None:
            st.write(f"Arquivos lidos com sucesso! {len(df_consolidado)} linhas encontradas. Colunas padronizadas disponíveis:")
            st.code(list(df_consolidado.columns))
            
            contrato_atual = CONTRATO_PLANNING if modo == "Planning" else CONTRATO_NO_PLANNING
            dataframes_finais = {}
            processamento_ok = True

            with st.spinner("Extraindo e montando os CSVs finais..."):
                # Itera sobre cada CSV que queremos criar (ex: 'depara', 'driver', 'vehicle')
                for nome_csv, colunas_necessarias in contrato_atual.items():
                    
                    colunas_disponiveis = df_consolidado.columns
                    colunas_faltando = [col for col in colunas_necessarias if col not in colunas_disponiveis]
                    
                    if colunas_faltando:
                        st.error(f"**Erro ao gerar `{nome_csv}.csv`:** As seguintes colunas não foram encontradas: `{colunas_faltando}`")
                        processamento_ok = False
                    else:
                        df_extraido = df_consolidado[colunas_necessarias].copy()
                        df_extraido.dropna(how='all', inplace=True)
                        df_extraido.drop_duplicates(inplace=True)
                        
                        dataframes_finais[nome_csv] = df_extraido
                        st.write(f"✔️ `{nome_csv}.csv` montado com sucesso ({len(df_extraido)} linhas únicas).")

            if processamento_ok:
                st.success("Todos os CSVs foram gerados com sucesso!")

                try:
                    memory_zip = io.BytesIO()
                    with zipfile.ZipFile(memory_zip, 'w') as zf:
                        for nome, df in dataframes_finais.items():
                            zf.writestr(f"{nome}.csv", df.to_csv(index=False, encoding='utf-8'))
                    
                    memory_zip.seek(0)
                    
                    st.download_button(
                        label="Baixar todos os CSVs (ZIP)",
                        data=memory_zip,
                        file_name=f"CSVs_{modo.lower()}_{pd.Timestamp.now().strftime('%Y%m%d')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar o arquivo ZIP: {e}")
            else:
                st.warning("O processamento falhou. Ajuste seus arquivos de upload para incluir as colunas faltantes e tente novamente.")
