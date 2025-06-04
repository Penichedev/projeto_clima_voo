import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
from datetime import datetime
from io import BytesIO
import pandas as pd

# Carregar a chave da API do .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("⚠️ OPENAI_API_KEY não encontrada no .env.")
    st.stop()

# Autenticação simples
USUARIOS_AUTORIZADOS = {
    "usuario1": "senha123",
    "usuario2": "segredo456"
}

with st.sidebar:
    st.header("🔒 Acesso Restrito")
    login_user = st.text_input("Usuário")
    login_pass = st.text_input("Senha", type="password")
    login_ok = st.button("Entrar")

if not (login_user in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[login_user] == login_pass):
    st.warning("Informe credenciais válidas para continuar.")
    st.stop()

# Inicializa cliente OpenAI
client = OpenAI(api_key=api_key)

# Histórico por sessão
if "historico" not in st.session_state:
    st.session_state.historico = []

# Prompt de consulta
def gerar_clima_com_margem(aeroporto, horario, rota, niveis_voo, trimestres):
    prompt = f"""
Considere as seguintes informações fornecidas pelo usuário para gerar dados meteorológicos médios aplicáveis à operação aeronáutica:

1. Aeroporto de interesse: {aeroporto}
2. Horário da decolagem: {horario} (local ou UTC)
3. Rota planejada: {rota}
4. Níveis de voo por trecho: {niveis_voo}
5. Trimestres selecionados: {', '.join(trimestres)}

Com base nessas informações, forneça:

- Temperatura média e ajuste QNH esperados para o horário informado no aeroporto de decolagem, utilizando climatologia histórica, dados oficiais e conversão correta para UTC conforme o fuso do aeroporto.
- Para cada trecho da rota informado, apresente:
   - O componente médio do vento (W/C), já ajustado com margem de segurança de 85%
   - O desvio de temperatura em relação à atmosfera padrão (ISA DEV), também com margem de segurança

Formato de saída por trimestre:

QX  
W/C Mxxx     ISA DEV Pxx

Evite explicações adicionais — retorne apenas os dados solicitados, de forma objetiva, como se fosse um briefing técnico.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao consultar API: {e}"

# Exportações
def exportar_resultado(resposta, formato, nome_base):
    if formato == "TXT":
        return resposta.encode("utf-8"), f"{nome_base}.txt"

    elif formato == "XML":
        xml = f"<?xml version='1.0'?><consulta><resultado><![CDATA[{resposta}]]></resultado></consulta>"
        return xml.encode("utf-8"), f"{nome_base}.xml"

    elif formato == "PDF":
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        for line in resposta.splitlines():
            pdf.cell(200, 5, txt=line, ln=True)
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        return buffer, f"{nome_base}.pdf"

    elif formato == "Excel":
        linhas = resposta.strip().split("\n")
        dados = [l.split() for l in linhas if l.strip() and not l.startswith("Q")]
        colunas = ["Coluna1", "Coluna2", "Coluna3"][:max(map(len, dados))]
        df = pd.DataFrame(dados, columns=colunas)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Resultados")
        buffer.seek(0)
        return buffer, f"{nome_base}.xlsx"

    else:
        return resposta.encode("utf-8"), f"{nome_base}.txt"

# UI
st.set_page_config(page_title="Consulta Meteorológica", layout="centered")
st.title("🛫 Consulta Meteorológica com Margem de Segurança")

aeroporto_origem = st.text_input("Aeroporto (ICAO)", "SKBO")
horario_utc = st.time_input("Horário de Decolagem (UTC)")
rota = st.text_area("Rota (fixos, aerovias, ICAO)", height=100)
fls = st.text_input("Níveis de voo por ponto (ex: TERAS/F340 JCL/F360)", "")
trimestres = st.multiselect("Selecione um ou mais trimestres", ["Q1", "Q2", "Q3", "Q4"])

if st.button("Consultar"):
    if not aeroporto_origem or not rota or not fls or not trimestres:
        st.warning("⚠️ Preencha todos os campos antes de consultar.")
    else:
        resposta = gerar_clima_com_margem(aeroporto_origem, horario_utc, rota, fls, trimestres)
        st.markdown("### 📊 Estimativas com Margem de Segurança (85%) – Resultado:")
        st.code(resposta, language="markdown")

        st.session_state.historico.append({
            "usuario": login_user,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "aeroporto": aeroporto_origem,
            "resultado": resposta
        })

        formato = st.selectbox("Escolha o formato para exportar:", ["TXT", "XML", "PDF", "Excel"])
        if st.button("📥 Exportar Resultado"):
            nome_base = f"consulta_{aeroporto_origem}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            arquivo, nome = exportar_resultado(resposta, formato, nome_base)
            st.download_button(f"⬇️ Baixar como {formato}", data=arquivo, file_name=nome, mime="application/octet-stream")

if st.checkbox("📄 Mostrar histórico da sessão"):
    if st.session_state.historico:
        for h in reversed(st.session_state.historico):
            st.markdown(f"**Usuário:** {h['usuario']}  |  **Data:** {h['data']}  |  **Aeroporto:** {h['aeroporto']}")
            st.code(h['resultado'], language="markdown")
            st.markdown("---")
    else:
        st.info("Nenhuma consulta realizada nesta sessão.")
