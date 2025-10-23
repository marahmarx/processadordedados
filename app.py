import streamlit as st
import pandas as pd
import io
import zipfile
import json     # Biblioteca nativa (não usada para salvar, mas boa prática)

# --- 1. CONFIGURAÇÃO (Contratos e Campos Obrigatórios) ---
st.set_page_config(page_title="Processador de Dados", layout="wide")
st.title("Ferramenta de Mapeamento e Geração de CSVs")
st.info("Siga os 4 passos de cima para baixo. O mapeamento do Passo 2 será reiniciado se a página for atualizada.")

# --- CONTRATOS FINAIS UNIFICADOS ---
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

# --- CAMPOS OBRIGATÓRIOS ---
CAMPOS_OBRIGATORIOS = ['pdv_ids', 'driver_id', 'vehicle_id']

# --- FUNÇÕES DO "MOTOR" ---

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
                # Padroniza colunas do usuário para minúsculas e sem espaços
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

# --- 3. INTERFACE PRINCIPAL (UMA PÁGINA) ---

# --- PASSO 1: SELECIONE O MODO DE SAÍDA ---
st.subheader("Passo 1: Selecione o Modo de Saída")
st.write("Isso define quais campos de mapeamento aparecerão abaixo.")

modo = st.radio(
    "Qual o tipo de saída você quer gerar?",
    ("Planning", "No Planning"),
    key='modo_processar',
    horizontal=True
)
contrato_atual = CONTRATO_PLANNING if modo == "Planning" else CONTRATO_NO_PLANNING
colunas_alvo_necessarias = sorted(list(set(col for cols in contrato_atual.values() for col in cols)))

st.divider()

# --- PASSO 2: PREENCHA O MAPEAMENTO (DE-PARA) ---
st.subheader("Passo 2: Preencha o Mapeamento (DE-PARA)")
st.write("Digite o nome da coluna no **SEU** arquivo que corresponde a cada campo do sistema.")
st.caption("Ex: Se o sistema pede `pdv_ids` e sua coluna se chama `poc`, digite `poc` no campo.")

mapeamento_para_salvar = {} # Formato: {'nome_no_seu_arquivo': 'nome_do_sistema'}
colunas_obrigatorias_faltando = []

col_form_1, col_form_2 = st.columns(2)

for i, col_sistema in enumerate(colunas_alvo_necessarias):
    label = f"Seu nome para: **{col_sistema}**"
    is_obrigatorio = col_sistema in CAMPOS_OBRIGATORIOS
    
    if is_obrigatorio:
        label += " (Obrigatório)"
    
    col_atual = col_form_1 if i % 2 == 0 else col_form_2
    
    # Campo de texto para o usuário digitar o nome da coluna dele
    user_name = col_atual.text_input(label, key=f"map_{col_sistema}")
    
    if user_name:
        user_name_clean = user_name.lower().strip()
        # Formato do rename: {'nome_do_usuario': 'nome_do_sistema'}
        mapeamento_para_salvar[user_name_clean] = col_sistema
    elif is_obrigatorio:
        colunas_obrigatorias_faltando.append(col_sistema)

st.divider()

# --- PASSO 3: CARREGUE SEUS ARQUIVOS DE DADOS ---
st.subheader("Passo 3: Carregue seus Arquivos de Dados")
uploaded_files = st.file_uploader(
    "Carregue seus arquivos (.csv, .xlsx) para processar",
    accept_multiple_files=True,
    type=['csv', 'xlsx'],
    key="uploader_dados"
)

st.divider()

# --- PASSO 4: PROCESSAR ---
st.subheader("Passo 4: Processe e Gere os Arquivos")

if st.button("Processar e Gerar CSVs", type="primary", use_container_width=True):
    
    # Validação 1: Mapeamento
    if colunas_obrigatorias_faltando:
        st.error(f"Erro: Você precisa preencher os seguintes campos obrigatórios no Passo 2: {colunas_obrigatorias_faltando}")
    
    # Validação 2: Arquivos
    elif not uploaded_files:
        st.error("Erro: Nenhum arquivo de dados carregado. Por favor, carregue seus arquivos no Passo 3.")
    
    # Se tudo OK, processa
    else:
        try:
            mapeamento_invertido_para_rename = mapeamento_para_salvar
            
            with st.spinner("Lendo e consolidando seus arquivos de dados..."):
                df_consolidado = carregar_e_concatenar(uploaded_files)
            
            if df_consolidado is not None:
                st.write(f"Arquivos lidos! {len(df_consolidado)} linhas encontradas.")
                
                # Aplica o mapeamento (renomeia as colunas do usuário)
                df_mapeado = df_consolidado.rename(columns=mapeamento_invertido_para_rename)
                
                dataframes_finais = {}
                processamento_ok = True
                
                with st.spinner("Montando os CSVs finais..."):
                    # Itera sobre cada CSV que queremos criar
                    for nome_csv, colunas_necessarias in contrato_atual.items():
                        
                        if not all(col in df_mapeado.columns for col in colunas_necessarias):
                            col_faltantes_final = [c for c in colunas_necessarias if c not in df_mapeado.columns]
                            st.error(f"Erro ao gerar {nome_csv}.csv: Colunas não encontradas: {col_faltantes_final}")
                            st.info(f"Verifique se você digitou os nomes corretamente no mapeamento do Passo 2.")
                            processamento_ok = False
                        else:
                            # Extrai as colunas
                            df_extraido = df_mapeado[colunas_necessarias].copy()
                            df_extraido.dropna(how='all', inplace=True)
                            df_extraido.drop_duplicates(inplace=True)
                            dataframes_finais[nome_csv] = df_extraido
                            st.write(f"✔️ `{nome_csv}.csv` montado com sucesso ({len(df_extraido)} linhas únicas).")

                if processamento_ok:
                    # Gera o ZIP
                    memory_zip = io.BytesIO()
                    with zipfile.ZipFile(memory_zip, 'w') as zf:
                        for nome, df in dataframes_finais.items():
                            zf.writestr(f"{nome}.csv", df.to_csv(index=False, encoding='utf-8'))
                    memory_zip.seek(0)
                    
                    st.success("Processamento concluído com sucesso!")
                    st.download_button(
                        label="Baixar todos os CSVs (ZIP)",
                        data=memory_zip,
                        file_name=f"CSVs_{modo.lower()}_{pd.Timestamp.now().strftime('%Y%m%d')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
            
        except Exception as e:
            st.error(f"Ocorreu um erro durante o processamento: {e}")
