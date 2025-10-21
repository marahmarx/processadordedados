import streamlit as st
import pandas as pd
import io
import zipfile

# --- 1. CONFIGURAÇÃO DA PÁGINA E DOS "CONTRATOS" ---
st.set_page_config(page_title="Processador de Dados Inteligente", layout="wide")
st.title("Ferramenta de Extração e Geração de CSVs")

# Estes são os "contratos" dos arquivos FINAIS que queremos gerar.
# As colunas foram extraídas dos arquivos de exemplo que você enviou.
CONTRATO_PLANNING = {
    'DEPARA': ['PDV_ids', 'driver_id'],
    'driver': ['driver_id', 'display_id', 'name', 'phone', 'document', 'active', 'logistic_operator_id', 'dc_id'],
    'vehicle': ['vehicle_id', 'display_id', 'plate', 'type', 'state', 'active', 'dc_id', 'logistic_operator_id']
}

CONTRATO_NO_PLANNING = {
    'tour': ['tour_id', 'date', 'display_id', 'dc_id', 'driver_id', 'vehicle_id', 'order_ids', 'trip_external_id', 'trip_display_id', 'trip_expected_start_timestamp'],
    'driver': ['driver_id', 'display_id', 'name', 'phone', 'document', 'active', 'logistic_operator_id', 'dc_id'],
    'vehicle': ['vehicle_id', 'display_id', 'plate', 'type', 'state', 'active', 'dc_id', 'logistic_operator_id']
}

# --- 2. INTERFACE - INSTRUÇÕES E SELEÇÃO DE MODO ---

# Usamos um "expander" para não poluir a tela.
with st.expander("Clique aqui para ver as colunas necessárias em seus arquivos de upload"):
    st.info("Seu(s) arquivo(s) de upload devem conter, em algum lugar, todas as colunas listadas abaixo para o modo escolhido.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Modo Planning")
        st.markdown("**Para o CSV `DEPARA`:**")
        st.code(CONTRATO_PLANNING['DEPARA'])
        st.markdown("**Para o CSV `driver`:**")
        st.code(CONTRATO_PLANNING['driver'])
        st.markdown("**Para o CSV `vehicle`:**")
        st.code(CONTRATO_PLANNING['vehicle'])

    with col2:
        st.subheader("Modo No Planning")
        st.markdown("**Para o CSV `tour`:**")
        st.code(CONTRATO_NO_PLANNING['tour'])
        st.markdown("**Para o CSV `driver`:**")
        st.code(CONTRATO_NO_PLANNING['driver'])
        st.markdown("**Para o CSV `vehicle`:**")
        st.code(CONTRATO_NO_PLANNING['vehicle'])

modo = st.radio(
    "1. Selecione o modo de operação:",
    ("Planning", "No Planning"),
    key='modo_operacao',
    horizontal=True
)

st.divider()

# --- 3. INTERFACE - UPLOAD ÚNICO E INTELIGENTE ---

st.subheader("2. Faça o upload dos seus arquivos de dados")
st.write("Você pode enviar um ou mais arquivos (Excel ou CSV). O sistema irá juntar e extrair as informações necessárias.")

uploaded_files = st.file_uploader(
    "Arraste e solte ou clique para selecionar os arquivos",
    accept_multiple_files=True,
    key='file_uploader'
)

st.divider()

# --- 4. LÓGICA DE PROCESSAMENTO ---

def carregar_e_concatenar(lista_arquivos):
    """Lê uma lista de arquivos e junta todos em um único DataFrame."""
    if not lista_arquivos:
        return None
    
    lista_dfs = []
    for file in lista_arquivos:
        try:
            # Tenta ler como Excel, se não conseguir, tenta como CSV
            try:
                df = pd.read_excel(file)
            except Exception:
                file.seek(0) # Volta ao início do arquivo para a nova leitura
                df = pd.read_csv(file)
            lista_dfs.append(df)
        except Exception as e:
            st.error(f"Não foi possível ler o arquivo '{file.name}'. Verifique o formato. Erro: {e}")
            return None
    
    # Concatena todos os dataframes, ignorando o índice para não ter duplicatas
    df_completo = pd.concat(lista_dfs, ignore_index=True)
    return df_completo

if uploaded_files:
    if st.button("Processar e Gerar CSVs", type="primary", use_container_width=True):
        
        with st.spinner("Lendo e consolidando seus arquivos..."):
            df_consolidado = carregar_e_concatenar(uploaded_files)

        if df_consolidado is not None:
            st.success(f"Arquivos lidos com sucesso! Encontramos um total de {len(df_consolidado)} linhas.")
            
            contrato_atual = CONTRATO_PLANNING if modo == "Planning" else CONTRATO_NO_PLANNING
            dataframes_finais = {}
            processamento_ok = True

            with st.spinner("Extraindo e montando os CSVs finais..."):
                # Itera sobre cada CSV que queremos criar (ex: 'DEPARA', 'driver', 'vehicle')
                for nome_csv, colunas_necessarias in contrato_atual.items():
                    
                    # Verifica se todas as colunas necessárias existem na base consolidada
                    colunas_disponiveis = df_consolidado.columns
                    colunas_faltando = [col for col in colunas_necessarias if col not in colunas_disponiveis]
                    
                    if colunas_faltando:
                        st.error(f"**Erro ao gerar `{nome_csv}.csv`:** As seguintes colunas não foram encontradas nos seus arquivos: `{colunas_faltando}`")
                        processamento_ok = False
                    else:
                        # Se todas as colunas existem, extrai e limpa
                        df_extraido = df_consolidado[colunas_necessarias].copy()
                        df_extraido.drop_duplicates(inplace=True)
                        dataframes_finais[nome_csv] = df_extraido
                        st.write(f"✔️ `{nome_csv}.csv` montado com sucesso ({len(df_extraido)} linhas únicas).")

            if processamento_ok:
                st.success("Todos os CSVs foram gerados com sucesso!")

                # Gera o arquivo ZIP para download
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
