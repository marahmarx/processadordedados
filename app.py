import streamlit as st
import pandas as pd
import io
import zipfile
import json     # Biblioteca nativa para ler/escrever o JSON

# --- 1. CONFIGURAÇÃO (Contratos e Campos Obrigatórios) ---
st.set_page_config(page_title="Processador de Dados", layout="wide")
st.title("Ferramenta de Mapeamento e Geração de CSVs")

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
# (O usuário DEVE preencher o mapeamento para estes)
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

# --- 2. INTERFACE PRINCIPAL COM ABAS ---

tab_processar, tab_configurar = st.tabs([
    "Processar Arquivos (Uso Diário)",
    "Configurar Mapeamento (Primeira Vez)"
])


# --- ABA DE CONFIGURAÇÃO (Onde o usuário "ensina" o app) ---
with tab_configurar:
    st.header("Passo 1: Ensine o Aplicativo")
    st.write("Preencha esta seção **uma vez** para criar seu arquivo de mapeamento. Você salvará este arquivo e o usará na aba 'Processar Arquivos' no futuro.")
    st.info("Preencha os campos com os nomes **exatos** das colunas como estão nos seus arquivos (ex: 'POC', 'ID do Motorista', 'Placa'). O sistema não diferencia maiúsculas/minúsculas.")
    
    st.subheader("Selecione o Modo para ver os campos:")
    modo_config = st.radio(
        "Para qual modo você quer gerar um mapeamento?",
        ("Planning", "No Planning"),
        key='modo_config',
        horizontal=True
    )
    
    contrato_config = CONTRATO_PLANNING if modo_config == "Planning" else CONTRATO_NO_PLANNING
    colunas_alvo_config = sorted(list(set(col for cols in contrato_config.values() for col in cols)))
    
    mapeamento_para_salvar = {} # Formato: {'nome_no_seu_arquivo': 'nome_do_sistema'}
    colunas_obrigatorias_faltando = []

    st.subheader("Preencha o DE-PARA:")
    # Cria duas colunas para o formulário não ficar tão longo
    col_form_1, col_form_2 = st.columns(2)
    
    for i, col_sistema in enumerate(colunas_alvo_config):
        label = f"Seu nome para: **{col_sistema}**"
        is_obrigatorio = col_sistema in CAMPOS_OBRIGATORIOS
        
        if is_obrigatorio:
            label += " (Obrigatório)"
        
        # Alterna entre as colunas do formulário
        col_atual = col_form_1 if i % 2 == 0 else col_form_2
        
        # Usa a chave (key) para podermos ler o valor depois
        user_name = col_atual.text_input(label, key=f"map_{col_sistema}")
        
        # Processa o nome que o usuário inseriu
        if user_name:
            user_name_clean = user_name.lower().strip()
            # Formato do rename: {'nome_do_usuario': 'nome_do_sistema'}
            mapeamento_para_salvar[user_name_clean] = col_sistema
        elif is_obrigatorio:
            colunas_obrigatorias_faltando.append(col_sistema)

    st.divider()
    
    if st.button("Gerar Arquivo de Mapeamento", type="primary"):
        if colunas_obrigatorias_faltando:
            st.error(f"Você precisa preencher os seguintes campos obrigatórios: {colunas_obrigatorias_faltando}")
        else:
            # Converte o dicionário de mapeamento para uma string JSON
            json_string = json.dumps(mapeamento_para_salvar, indent=2)
            st.success("Mapeamento gerado! Baixe o arquivo e guarde-o em um local seguro.")
            st.download_button(
                label="Baixar config.json",
                data=json_string,
                file_name=f"config_{modo_config.lower()}.json",
                mime="application/json"
            )


# --- ABA DE PROCESSAMENTO (Onde o usuário trabalha) ---
with tab_processar:
    st.header("Passo 1: Carregar Arquivos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        mapping_file = st.file_uploader("Carregue seu 'config.json' salvo", type=['json'])
    
    with col2:
        uploaded_files = st.file_uploader(
            "Carregue seus arquivos de DADOS (.csv, .xlsx)",
            accept_multiple_files=True,
            type=['csv', 'xlsx']
        )
    
    st.header("Passo 2: Processar")
    
    # Seleciona o modo para saber QUAIS CSVs gerar
    modo_processar = st.radio(
        "Qual o tipo de saída você quer gerar?",
        ("Planning", "No Planning"),
        key='modo_processar',
        horizontal=True
    )
    contrato_processar = CONTRATO_PLANNING if modo_processar == "Planning" else CONTRATO_NO_PLANNING

    st.divider()

    if st.button("Processar e Gerar CSVs", type="primary", use_container_width=True):
        
        # Validação inicial
        if not mapping_file:
            st.error("Erro: Por favor, carregue seu arquivo 'config.json' de mapeamento.")
        elif not uploaded_files:
            st.error("Erro: Por favor, carregue um ou mais arquivos de dados.")
        else:
            try:
                # Carrega o mapeamento
                mapeamento_invertido_para_rename = json.load(mapping_file)
                
                # Carrega os dados
                with st.spinner("Lendo e consolidando seus arquivos..."):
                    df_consolidado = carregar_e_concatenar(uploaded_files)
                
                if df_consolidado is not None:
                    st.write(f"Arquivos lidos! {len(df_consolidado)} linhas encontradas.")
                    
                    # Aplica o mapeamento (renomeia as colunas do usuário)
                    df_mapeado = df_consolidado.rename(columns=mapeamento_invertido_para_rename)
                    
                    dataframes_finais = {}
                    processamento_ok = True
                    
                    with st.spinner("Montando os CSVs finais..."):
                        # Itera sobre cada CSV que queremos criar
                        for nome_csv, colunas_necessarias in contrato_processar.items():
                            
                            if not all(col in df_mapeado.columns for col in colunas_necessarias):
                                col_faltantes_final = [c for c in colunas_necessarias if c not in df_mapeado.columns]
                                st.error(f"Erro ao gerar {nome_csv}.csv: Colunas não encontradas: {col_faltantes_final}")
                                st.info(f"Seu 'config.json' pode estar desatualizado ou não mapeou estas colunas.")
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
                            file_name=f"CSVs_{modo_processar.lower()}_{pd.Timestamp.now().strftime('%Y%m%d')}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                
            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento: {e}")
