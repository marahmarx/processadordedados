import streamlit as st
import pandas as pd
import io
import zipfile
from fuzzywuzzy import process # Importa a biblioteca de sugestão

# --- 1. CONFIGURAÇÃO (Contratos 100% em minúsculas) ---
st.set_page_config(page_title="Processador de Dados Inteligente", layout="wide")
st.title("Ferramenta de Mapeamento e Geração de CSVs")

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
                df = pd.read_csv(file)
                if df.shape[1] == 1:
                    file.seek(0)
                    df = pd.read_csv(file, sep=';')
            
            if df is not None:
                df.columns = df.columns.str.lower().str.strip()
                lista_dfs.append(df)
            else:
                st.error(f"Não foi possível processar o arquivo '{file_name}'.")
                return None
        except Exception as e:
            st.error(f"Não foi possível ler o arquivo '{file_name}'. Erro: {e}")
            return None
    
    if not lista_dfs:
        return None
        
    return pd.concat(lista_dfs, ignore_index=True)

def encontrar_melhor_palpite(coluna_alvo, colunas_do_usuario):
    """Usa fuzzywuzzy para encontrar a coluna do usuário que mais se parece com a coluna alvo."""
    # Tenta uma correspondência exata primeiro (ignorando maiúsculas/minúsculas)
    if coluna_alvo in colunas_do_usuario:
        return coluna_alvo
    
    # Se não achar, usa o "fuzzy matching" para encontrar a mais parecida
    # O process.extractOne retorna (melhor_palpite, score_de_similaridade)
    melhor_palpite, score = process.extractOne(coluna_alvo, colunas_do_usuario)
    
    # Só aceita o palpite se a similaridade for razoável (ex: > 70%)
    if score > 70:
        return melhor_palpite
    return None # Não sugere nada se não for parecido

# --- 3. INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
# O Streamlit esquece de tudo a cada clique. Precisamos salvar o estado.
if 'mapeamento_confirmado' not in st.session_state:
    st.session_state.mapeamento_confirmado = False
if 'mapeamento_final' not in st.session_state:
    st.session_state.mapeamento_final = {}
if 'df_consolidado' not in st.session_state:
    st.session_state.df_consolidado = None

# --- 4. INTERFACE PRINCIPAL ---

# Etapa 1: Seleção de Modo
modo = st.radio(
    "1. Selecione o modo de operação:",
    ("Planning", "No Planning"),
    key='modo_operacao',
    horizontal=True,
    disabled=st.session_state.mapeamento_confirmado # Desativa se já mapeou
)

# Define o contrato com base no modo
contrato_atual = CONTRATO_PLANNING if modo == "Planning" else CONTRATO_NO_PLANNING

# Pega a lista de TODAS as colunas únicas que precisamos para este modo
colunas_alvo_necessarias = set()
for col_list in contrato_atual.values():
    colunas_alvo_necessarias.update(col_list)
colunas_alvo_necessarias = sorted(list(colunas_alvo_necessarias))

# Etapa 2: Upload (só aparece se o mapeamento não foi feito)
if not st.session_state.mapeamento_confirmado:
    st.subheader("2. Faça o upload dos seus arquivos de dados")
    st.write("Envie um ou mais arquivos (Excel ou CSV). O sistema tentará adivinhar suas colunas.")
    
    uploaded_files = st.file_uploader(
        "Arraste e solte ou clique para selecionar os arquivos",
        accept_multiple_files=True,
        key='file_uploader',
        type=['csv', 'xlsx']
    )
    
    if uploaded_files:
        with st.spinner("Lendo e consolidando seus arquivos..."):
            st.session_state.df_consolidado = carregar_e_concatenar(uploaded_files)
        
        if st.session_state.df_consolidado is not None:
            st.success("Arquivos lidos com sucesso!")
            st.subheader("3. Mapeamento de Colunas")
            st.write("Confirme ou corrija as sugestões do sistema.")
            
            colunas_do_usuario = list(st.session_state.df_consolidado.columns)
            mapeamento_sugerido = {}
            
            # Cria o formulário de mapeamento
            with st.form(key="form_mapeamento"):
                st.write("Para cada **Coluna que o Sistema Precisa**, selecione a **Coluna do Seu Arquivo** correspondente.")
                
                # Para cada coluna que o sistema precisa...
                for col_alvo in colunas_alvo_necessarias:
                    # ...encontra o melhor palpite nas colunas do usuário
                    palpite = encontrar_melhor_palpite(col_alvo, colunas_do_usuario)
                    
                    # Acha o índice do palpite na lista de opções para o selectbox
                    try:
                        indice = colunas_do_usuario.index(palpite) if palpite is not None else 0
                    except ValueError:
                        indice = 0 # Segurança se o palpite não estiver na lista
                    
                    # Opções para o dropdown: "Nenhuma" + todas as colunas do usuário
                    opcoes = ["-- Ignorar --"] + colunas_do_usuario
                    
                    # Ajusta o índice se "Nenhuma" for a opção (índice 0)
                    if palpite is not None:
                        indice = opcoes.index(palpite)
                    else:
                        indice = 0 # Default para "-- Ignorar --"

                    # Mostra o dropdown
                    mapeamento_sugerido[col_alvo] = st.selectbox(
                        f"Coluna que o Sistema Precisa: **{col_alvo}**",
                        options=opcoes,
                        index=indice
                    )
                
                # Botão de submissão do formulário
                submitted = st.form_submit_button("Confirmar Mapeamento e Processar")
                
                if submitted:
                    # Processa o mapeamento
                    mapeamento_invertido = {}
                    colunas_faltando = []
                    
                    for col_alvo, col_usuario in mapeamento_sugerido.items():
                        if col_usuario == "-- Ignorar --":
                            colunas_faltando.append(col_alvo)
                        else:
                            # O formato final é {col_usuario: col_alvo} para o .rename()
                            mapeamento_invertido[col_usuario] = col_alvo
                            
                    if colunas_faltando:
                        st.error(f"Mapeamento incompleto! Você precisa mapear as seguintes colunas: {colunas_faltando}")
                    else:
                        st.session_state.mapeamento_final = mapeamento_invertido
                        st.session_state.mapeamento_confirmado = True
                        st.success("Mapeamento confirmado! Processando...")
                        st.experimental_rerun() # Roda o script de novo

# Etapa 3: Processamento e Download (só aparece se o mapeamento foi confirmado)
if st.session_state.mapeamento_confirmado:
    
    st.subheader("3. Processamento e Download")
    
    df_mapeado = st.session_state.df_consolidado.rename(
        columns=st.session_state.mapeamento_final
    )
    
    st.write("Colunas renomeadas e prontas para processar:")
    st.code(list(df_mapeado.columns))
    
    dataframes_finais = {}
    processamento_ok = True
    
    with st.spinner("Montando os CSVs finais..."):
        # Itera sobre cada CSV que queremos criar
        for nome_csv, colunas_necessarias in contrato_atual.items():
            
            # Checa se temos todas as colunas após o mapeamento
            if not all(col in df_mapeado.columns for col in colunas_necessarias):
                st.error(f"Erro ao gerar {nome_csv}.csv. Mesmo após o mapeamento, nem todas as colunas foram encontradas.")
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

    # Botão para recomeçar o processo
    if st.button("Recomeçar / Enviar novos arquivos"):
        st.session_state.mapeamento_confirmado = False
        st.session_state.mapeamento_final = {}
        st.session_state.df_consolidado = None
        st.experimental_rerun()
