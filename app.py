import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from openai import OpenAI

# ----- CONFIG BÁSICA -----
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

st.set_page_config(
    page_title="SEO Otimizator",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 SEO Otimizator (Google + OpenAI)")
st.markdown(
    "Analisa SEO on-page e, se disponível, cruza com dados reais do Google Search Console."
)

# ----- SECRETS -----
openai_key = st.secrets.get("OPENAI_API_KEY")
gsc_client_id = st.secrets.get("GSC_CLIENT_ID")
gsc_client_secret = st.secrets.get("GSC_CLIENT_SECRET")

# ----- SIDEBAR -----
st.sidebar.header("Configuração")

if openai_key:
    st.sidebar.success("OpenAI API Key OK")
else:
    st.sidebar.error("OPENAI_API_KEY não configurada")

use_gsc = False
if gsc_client_id and gsc_client_secret:
    use_gsc = st.sidebar.checkbox("Usar Google Search Console", value=True)
else:
    st.sidebar.info("Google GSC não configurado (opcional)")

gsc_property = None
if use_gsc:
    gsc_property = st.sidebar.text_input(
        "Propriedade do Search Console",
        placeholder="https://www.teusite.pt/"
    )

st.sidebar.markdown(
    """
**Funcionalidades**
- Análise SEO on-page
- Sugestões com IA
- Queries reais do Google (opcional)
"""
)

# ----- GOOGLE SEARCH CONSOLE -----
def get_gsc_service():
    client_config = {
        "installed": {
            "client_id": gsc_client_id,
            "client_secret": gsc_client_secret,
            "redirect_uris": ["http://localhost"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    service = build("searchconsole", "v1", credentials=creds)
    return service


def fetch_gsc_queries(service, site_url, days=28):
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)

    request = {
        "startDate": str(start_date),
        "endDate": str(end_date),
        "dimensions": ["QUERY"],
        "rowLimit": 100,
    }

    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body=request)
        .execute()
    )

    rows = response.get("rows", [])
    data = []

    for r in rows:
        data.append({
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        })

    return pd.DataFrame(data)

# ----- ANALISAR HTML -----
def analyze_page(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.string.strip() if soup.title else ""

    meta_desc = ""
    for m in soup.find_all("meta"):
        if m.get("name") == "description":
            meta_desc = (m.get("content") or "").strip()
            break

    h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]

    text = " ".join(
        [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    )

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "h2": h2,
        "word_count": len(text.split()),
        "raw_text": text[:4000],
    }

# ----- OPENAI -----
def get_openai_suggestions(openai_key, page_data, niche, gsc_df=None):
    client = OpenAI(api_key=openai_key)

    gsc_text = ""
    if gsc_df is not None and not gsc_df.empty:
        gsc_text = f"\nDADOS DO GOOGLE SEARCH CONSOLE:\n{gsc_df.head(15).to_string(index=False)}"

    prompt = f"""
És um consultor sénior de SEO em Portugal.

Objetivo: melhorar o SEO orgânico da página para o nicho "{niche}".

DADOS DA PÁGINA:
- Title: {page_data['title']}
- Meta description: {page_data['meta_description']}
- H1: {page_data['h1']}
- H2: {page_data['h2']}
- Nº de palavras: {page_data['word_count']}
- Texto: {page_data['raw_text']}

{gsc_text}

Tarefas:
1. Lista 10 keywords prioritárias (tabela).
2. Sugere novo title (≤60 chars) e meta description (≤155).
3. Indica melhorias on-page (conteúdo + estrutura).
4. Identifica oportunidades com base em CTR/posição (se houver GSC).
5. Sugere 3 novas páginas/artigos estratégicos.

Responde em PT-PT, bem estruturado.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return response.choices[0].message.content

# ----- UI -----
col1, col2 = st.columns(2)

with col1:
    url = st.text_input("URL da página", placeholder="https://www.teusite.pt/")
with col2:
    niche = st.text_input("Nicho / intenção", placeholder="ex: canalizador Lisboa")

st.markdown("---")

if st.button("🔍 Analisar SEO"):
    if not url or not niche:
        st.error("Preenche a URL e o nicho.")
    elif not openai_key:
        st.error("OPENAI_API_KEY não configurada.")
    elif use_gsc and not gsc_property:
        st.error("Indica a propriedade do Search Console.")
    else:
        try:
            with st.spinner("A analisar HTML..."):
                page_data = analyze_page(url)

            gsc_df = None
            if use_gsc:
                with st.spinner("A ligar ao Google Search Console..."):
                    service = get_gsc_service()
                    gsc_df = fetch_gsc_queries(service, gsc_property)

                st.subheader("🔍 Google Search Console")
                if gsc_df.empty:
                    st.warning("Sem dados no GSC.")
                else:
                    st.dataframe(gsc_df)

            with st.spinner("🤖 A gerar recomendações SEO..."):
                suggestions = get_openai_suggestions(
                    openai_key, page_data, niche, gsc_df
                )

            st.subheader("📈 Recomendações SEO")
            st.write(suggestions)

        except Exception as e:
            st.error("Erro durante a análise.")
            st.exception(e)

st.info(
    "Ferramenta para uso próprio. GSC é opcional mas recomendado."
)
