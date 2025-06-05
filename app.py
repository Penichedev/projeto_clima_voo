import streamlit as st
st.set_page_config(page_title="Consulta Meteorológica", layout="centered")

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

def gerar_clima_com_margem(origem, destino, horario, rota, niveis_voo, trimestres):
    prompt = f"""
Considere as seguintes informações fornecidas pelo usuário para gerar dados meteorológicos médios aplicáveis à operação aeronáutica:

1. Aeroporto de origem: {origem}
2. Aeroporto de destino: {destino if destino else 'N/A'}
3. Horário da decolagem: {horario} (local ou UTC)
4. Rota planejada: {rota if rota else 'Consulta local apenas'}
5. Níveis de voo por trecho: {niveis_voo if niveis_voo else 'N/A'}
6. Trimestres selecionados: {', '.join(trimestres)}

Com base nessas informações, forneça:

- Temperatura média e ajuste QNH esperados para o aeroporto de origem, considerando o horário informado e climatologia histórica.
- Caso uma rota seja fornecida, apresente também:
   - O componente médio do vento (W/C) por trecho e nível de voo, ajustado com margem de segurança de 85%
   - O desvio de temperatura ISA DEV por nível, também com margem de segurança

Formato de saída por trimestre:

QX  
W/C Mxxx     ISA DEV Pxx

Retorne apenas os dados solicitados, como em um briefing técnico.
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
st.title("🛫 Consulta Meteorológica com Margem de Segurança")

origem = st.text_input("Aeroporto de Origem (ICAO)", "SKBO")
destino = st.text_input("Aeroporto de Destino (ICAO)", "SCEL")
horario_utc = st.time_input("Horário de Decolagem (UTC)")
rota = st.text_area("Rota (fixos, aerovias, ICAO)", height=100)
fls = st.text_input("Níveis de voo por ponto (ex: TERAS/F340 JCL/F360)", "")
trimestres = st.multiselect("Selecione um ou mais trimestres", ["Q1", "Q2", "Q3", "Q4"])

if st.button("Consultar"):
    if not origem or not trimestres:
        st.warning("⚠️ Informe pelo menos a origem e o(s) trimestre(s).")
    else:
        resposta = gerar_clima_com_margem(origem, destino, horario_utc, rota, fls, trimestres)
        st.markdown("### 📊 Resultado da Consulta Meteorológica")
        st.code(resposta, language="markdown")

        st.session_state.historico.append({
            "usuario": login_user,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "aeroporto": origem,
            "resultado": resposta
        })

        formato = st.selectbox("Escolha o formato para exportar:", ["TXT", "XML", "PDF", "Excel"])
        if st.button("📥 Exportar Resultado"):
            nome_base = f"consulta_{origem}_{datetime.now().strftime('%Y%m%d_%H%M')}"
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
