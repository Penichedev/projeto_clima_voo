import streamlit as st
st.set_page_config(page_title="Meteorological Briefing", layout="centered")

import os
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
from datetime import datetime
from io import BytesIO
import pandas as pd

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("⚠️ OPENAI_API_KEY not found in .env.")
    st.stop()

USERS = {
    "user1": "pass123",
    "user2": "secure456"
}

with st.sidebar:
    st.header("🔒 Login")
    login_user = st.text_input("Username")
    login_pass = st.text_input("Password", type="password")
    login_ok = st.button("Login")

if not (login_user in USERS and USERS[login_user] == login_pass):
    st.warning("Please provide valid credentials.")
    st.stop()

client = OpenAI(api_key=api_key)

if "history" not in st.session_state:
    st.session_state.history = []

def generate_prompt(dep, arr, time, route, levels, quarters, mode):
    margin_text = "with a conservative safety margin of 85% applied to wind and ISA deviation calculations" if mode == "Conservative" else "as raw climatological averages without applying safety margins"
    prompt = f"""
You are generating a meteorological and performance briefing based on historical climatological data.

1. Departure airport: {dep}
2. Arrival airport: {arr if arr else 'N/A'}
3. Departure time (UTC): {time}
4. Route: {route if route else 'N/A'}
5. Flight levels: {levels if levels else 'N/A'}
6. Periods selected: {', '.join(quarters)}
7. Estimation Mode: {mode}

Please provide:
- Average temperature and QNH for the departure airport at the indicated time.
- If route and flight levels are provided, return for each segment:
   - Wind component (W/C) and ISA deviation (ISA DEV), {margin_text}.

Format by quarter:
QX  
W/C Mxxx     ISA DEV Pxx

Return only the data, structured as an operational dispatch briefing.
"""
    return prompt

def query_openai(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"API error: {e}"

def export_result(content, format, name):
    if format == "TXT":
        return content.encode("utf-8"), f"{name}.txt"
    elif format == "XML":
        xml = f"<?xml version='1.0'?><briefing><content><![CDATA[{content}]]></content></briefing>"
        return xml.encode("utf-8"), f"{name}.xml"
    elif format == "PDF":
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        for line in content.splitlines():
            pdf.cell(200, 5, txt=line, ln=True)
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        return buffer, f"{name}.pdf"
    elif format == "Excel":
        lines = content.strip().split("\n")
        data = [l.split() for l in lines if l.strip() and not l.startswith("Q")]
        columns = ["Column1", "Column2", "Column3"][:max(map(len, data))]
        df = pd.DataFrame(data, columns=columns)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Briefing")
        buffer.seek(0)
        return buffer, f"{name}.xlsx"
    else:
        return content.encode("utf-8"), f"{name}.txt"

st.title("🌤️ Meteorological Briefing")

dep = st.text_input("Departure Airport (ICAO)", "SKBO")
arr = st.text_input("Arrival Airport (ICAO)", "SCEL")
dep_time = st.time_input("ETD (UTC)")
route = st.text_area("Route (waypoints, airways)", height=100)
levels = st.text_input("Flight levels per segment (e.g. TERAS/F340 JCL/F360)", "")
quarters = st.multiselect("Select Quarter(s)", ["Q1", "Q2", "Q3", "Q4"])
mode = st.radio("Estimation Mode", ["Raw", "Conservative"])

if st.button("Generate Briefing"):
    if not dep or not quarters:
        st.warning("Please provide at least the departure airport and quarter(s).")
    else:
        prompt = generate_prompt(dep, arr, dep_time, route, levels, quarters, mode)
        result = query_openai(prompt)
        st.markdown("### 📋 Briefing Result")
        st.code(result, language="markdown")

        st.session_state.history.append({
            "user": login_user,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "airport": dep,
            "result": result
        })

        fmt = st.selectbox("Export Format", ["TXT", "XML", "PDF", "Excel"])
        if st.button("📥 Download Briefing"):
            base = f"briefing_{dep}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            file, fname = export_result(result, fmt, base)
            st.download_button(f"⬇️ Download as {fmt}", data=file, file_name=fname, mime="application/octet-stream")

if st.checkbox("🕓 Show Session History"):
    if st.session_state.history:
        for h in reversed(st.session_state.history):
            st.markdown(f"**User:** {h['user']}  |  **Date:** {h['datetime']}  |  **Airport:** {h['airport']}")
            st.code(h['result'], language="markdown")
            st.markdown("---")
    else:
        st.info("No briefings generated in this session.")
