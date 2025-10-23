import streamlit as st
import pandas as pd
import io
import zipfile
import difflib # Biblioteca nativa do Python (sem erros de instalação)

# --- 1. CONFIGURAÇÃO (Contratos Unificados) ---
st.set_page_config(page_title="Processador de Dados Inteligente", layout="wide")
st.title("Ferramenta de Mapeamento e Geração de CSVs")

# --- CONTRATOS FINAIS UNIFICADOS ---
# Ambos os modos agora procuram por 'pdv_ids' (com D)
CONTRATO_PLANNING = {
    'depara': ['pdv_ids', 'driver_id'],
    'driver': ['driver_id', 'vehicle_id', 'document', 'dc_id', 'display_id', 'name', 'phone', 'active', 'logistic_operator_id'],
    'vehicle': ['vehicle_id', 'plate', 'dc_id', 'display_id', 'type', 'state', 'active', 'logistic_operator_id']
}

CONTRATO_NO_PLANNING = {
    'tour': ['pdv_ids', 'dc_id', 'vehicle_id', 'driver_id', 'date', 'order_id', 'tour_id', 'display_id', 'trip_external_id', 'trip_display_id', 'trip_expected_start_timestamp'],
    'driver': ['driver_id', 'vehicle_id', 'document', 'dc_id', 'display_id', 'name', 'phone', 'active', 'logistic_operator_id'],
    'vehicle': ['vehicle_id', 'plate', 'dc_id', 'display_id', 'type', 'state', 'active', 'logistic_operator_id']
}

# --- O "CÉREBRO" DA IA (DICIONÁRIO DE SINÔNIMOS) ---
# 'pdv_ids' é a chave principal. 'pvd_id' (com V) é apenas um sinônimo.
DICIONARIO_SINONIMOS = {
    'pdv_ids': ['pdv', 'poc', 'id_poc', 'pontodevenda', 'id_pvd', 'pvd_id'],
    'driver_id': ['id_driver', 'id_motorista', 'motorista'],
    'vehicle_id': ['id_vehicle', 'id_veiculo', 'carro', 'veiculo'],
    'dc_id': ['id_dc', 'cd', 'cdd'],
    'plate': ['placa'],
    'document': ['documento', 'cpf'],
    'date': ['data'],
    'order_id': ['id_order', 'id_pedido', 'pedido', 'order_ids']
    # Para "treinar", adicione mais sinônimos aqui
}

# --- CAMPOS OBRIGATÓRIOS ---
CAMPOS_OBRIGATORIOS = ['pdv_ids', 'driver_id', 'vehicle_id']


# --- 2. FUNÇÕES DO "MOTOR" ---

def carregar_e_concatenar(lista_arquivos):
    """Lê arquivos, padroniza colunas (minúsculas/strip) e junta em um DataFrame."""
    lista_dfs = []
    for file in lista_arquivos:
        df = None
        try:
            file_name = file.name
            if file_name.endswith('.xlsx'):
                df = pd.read_excel(file)
            elif file_name.endswith('.csv'):
                file.seek(0)
                df = pd.read_csv(file, low_memory=False)
                if df.shape[1] == 1:
                    file.seek(0)
                    df = pd.read_csv(file, sep=';', low_memory=False)
            
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
    return pd.concat(lista_dfs, ignore_index=True)

def encontrar_melhor_palpite(coluna_alvo, colunas_do_usuario):
    """A "IA" que adivinha a coluna."""
    # Nível 1: Correspondência Exata
    if coluna_alvo in colunas_do_usuario:
        return coluna_alvo
    # Nível 2: Correspondência por Sinônimo (Consulta o "Cérebro")
    if coluna_alvo in DICIONARIO_SINONIMOS:
        for sinonimo in DICIONARIO_SINONIMOS[coluna_alvo]:
            if sinonimo in colunas_do_usuario:
                return sinonimo # Encontrou um sinônimo!
    # Nível 3: Correspondência por Similaridade (Erros de digitação)
    palpites = difflib.get_close_matches(coluna_alvo, colunas_do_usuario, n=1, cutoff=0.7)
    if palpites:
        return palpites[0]
    return None

# --- 3. INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'etapa' not in st.session_state:
    st.session_state.etapa = "upload" # Controla o fluxo
if 'mapeamento_final' not in st.session_state:
    st.session_state.mapeamento_final = {}
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = None

# --- 4. INTERFACE PRINCIPAL ---

# Etapa 1: Instruções e Seleção de Modo
with st.expander("Clique aqui para ver os nomes de colunas IDEAIS que o sistema procura"):
    st.info("Não se preocupe se suas colunas tiverem nomes diferentes. A IA tentará adivinhar.")
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
    horizontal=True,
    disabled=(st.session_state.etapa != "upload")
)
contrato_atual = CONTRATO_PLANNING if modo == "Planning" else CONTRATO_NO_PLANNING
colunas_alvo_necessarias = sorted(list(set(col for cols in contrato_atual.values() for col in cols)))

st.divider()

# Etapa 2: Upload
if st.session_state.etapa == "upload":
    st.subheader("2. Faça o upload dos seus arquivos de dados")
    uploaded_files = st.file_uploader(
        "Envie um ou mais arquivos (Excel ou CSV).",
        accept_multiple_files=True,
        key='file_uploader',
        type=['csv', 'xlsx']
    )
    if uploaded_files:
        with st.spinner("Lendo e consolidando seus arquivos..."):
            st.session_state.df_consolidado = carregar_e_concatenar(uploaded_files)
        if st.session_state.df_consolidado is not None:
            st.session_state.etapa = "mapear" # Avança para a próxima etapa
            st.rerun()

# Etapa 3: Mapeamento (Supervisão da "IA")
if st.session_state.etapa == "mapear":
    st.subheader("2. Confirme o Mapeamento da IA")
    st.write("O sistema adivinhou suas colunas. Por favor, revise e confirme.")
    
    colunas_do_usuario = list(st.session_state.df_consolidado.columns)
    mapeamento_sugerido = {}
    
    with st.form(key="form_mapeamento"):
        for col_alvo in colunas_alvo_necessarias:
            palpite = encontrar_melhor_palpite(col_alvo, colunas_do_usuario)
            opcoes = ["-- Ignorar --"] + colunas_do_usuario
            try:
                indice = opcoes.index(palpite) if palpite is not None else 0
            except ValueError:
                indice = 0
            label = f"Coluna do Sistema: **{col_alvo}**"
            if col_alvo in CAMPOS_OBRIGATORIOS:
                label += " (Obrigatório)"
            mapeamento_sugerido[col_alvo] = st.selectbox(label, options=opcoes, index=indice)
        
        submitted = st.form_submit_button("Confirmar Mapeamento e Processar")
        
        if submitted:
            mapeamento_invertido = {}
            colunas_obrigatorias_faltando = []
            for col_alvo, col_usuario in mapeamento_sugerido.items():
                if col_usuario == "-- Ignorar --":
                    if col_alvo in CAMPOS_OBRIGATORIOS:
                        colunas_obrigatorias_faltando.append(col_alvo)
                else:
                    mapeamento_invertido[col_usuario] = col_alvo
                    
            if colunas_obrigatorias_faltando:
                st.error(f"Mapeamento incompleto! Você precisa mapear os campos obrigatórios: {colunas_obrigatorias_faltando}")
            else:
                st.session_state.mapeamento_final = mapeamento_invertido
                st.session_state.etapa = "processar"
                st.success("Mapeamento confirmado! Processando...")
                st.rerun()

# Etapa 4: Processamento e Download
if st.session_state.etapa == "processar":
    st.subheader("3. Processamento e Download")
    df_mapeado = st.session_state.df_consolidado.rename(columns=st.session_state.mapeamento_final)
    dataframes_finais = {}
    processamento_ok = True
    
    with st.spinner("Montando os CSVs finais..."):
        for nome_csv, colunas_necessarias in contrato_atual.items():
            if not all(col in df_mapeado.columns for col in colunas_necessarias):
                col_faltantes_final = [c for c in colunas_necessarias if c not in df_mapeado.columns]
                st.error(f"Erro ao gerar {nome_csv}.csv: Colunas não encontradas: {col_faltantes_final}")
                processamento_ok = False
            else:
                df_extraido = df_mapeado[colunas_necessarias].copy()
                df_extraido.dropna(how='all', inplace=True)
                df_extraido.drop_duplicates(inplace=True)
                dataframes_finais[nome_csv] = df_extraido
                st.write(f"✔️ `{nome_csv}.csv` montado com sucesso ({len(df_extraido)} linhas únicas).")

    if processamento_ok:
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

    if st.button("Recomeçar / Enviar novos arquivos"):
        st.session_state.etapa = "upload"
        st.session_state.mapeamento_final = {}
        st.session_state.df_consolidado = None
        st.rerun()
