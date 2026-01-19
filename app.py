import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from openai import OpenAI

# ----- CONFIG BÁSICA -----
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
st.set_page_config(page_title="SEO Otimizator", page_icon="🧠", layout="wide")
st.title("🧠 SEO Otimizator - Google + OpenAI (uso próprio)")

st.markdown(
    "Este app analisa o SEO dos **teus** sites usando Google Search Console e gera recomendações com OpenAI."
)

# ----- SIDEBAR -----
# Sidebar simples
st.sidebar.header("Status")
st.sidebar.info("OpenAI: ✅ Configurada")
st.sidebar.info("Google GSC: Configurar em Settings → Secrets")


st.sidebar.markdown(
    "É necessário ter um ficheiro `client_secret.json` na mesma pasta do app, criado na Google Cloud, com a Search Console API ativada."
)

# ----- GOOGLE SEARCH CONSOLE SERVICE -----
def get_gsc_service():
    # Usa secrets do Streamlit Cloud
    client_config = {
        "installed": {
            "client_id": st.secrets["GSC_CLIENT_ID"],
            "client_secret": st.secrets["GSC_CLIENT_SECRET"],
            "redirect_uris": ["http://localhost"]
        }
    }
    
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    service = build("searchconsole", "v1", credentials=creds)
    return service


# ----- BUSCAR QUERIES GSC -----
def fetch_gsc_queries(service, site_url, days=28):
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)
    request = {
        "startDate": str(start_date),
        "endDate": str(end_date),
        "dimensions": ["QUERY"],
        "rowLimit": 200,
        "startRow": 0,
    }
    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body=request)
        .execute()
    )
    rows = response.get("rows", [])
    data = []
    for r in rows:
        keys = r.get("keys", [""])
        data.append(
            {
                "query": keys[0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
            }
        )
    return pd.DataFrame(data)

# ----- ANALISAR PÁGINA (HTML) -----
def analyze_page(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.string.strip() if soup.title else ""

    meta_desc = ""
    for m in soup.find_all("meta"):
        if m.get("name") == "description":
            meta_desc = (m.get("content") or "").strip()
            break

    h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]

    text = " ".join([p.get_text(" ", strip=True) for p in soup.find_all("p")])
    word_count = len(text.split())

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "h2": h2,
        "word_count": word_count,
        "raw_text": text[:4000],  # limitar o que vai ao prompt
    }

# ----- OPENAI: RECOMENDAÇÕES -----
def get_openai_suggestions(openai_key, page_data, gsc_df, niche, locale="pt-PT"):
    client = OpenAI(api_key=openai_key)

    gsc_text = ""
    if gsc_df is not None and not gsc_df.empty:
        top_queries = (
            gsc_df.sort_values("impressions", ascending=False)
            .head(15)
            .to_dict(orient="records")
        )
        gsc_text = str(top_queries)

    prompt = f"""
    És um consultor sénior de SEO para Portugal ({locale}).

    Objetivo: avaliar a página abaixo para o nicho "{niche}" e propor melhorias para escalar o SEO (orgânico Google).

    DADOS DA PÁGINA:
    - Título: {page_data['title']}
    - Meta description: {page_data['meta_description']}
    - H1: {page_data['h1']}
    - H2: {page_data['h2']}
    - Nº de palavras: {page_data['word_count']}
    - Trecho de texto: {page_data['raw_text']}

    DADOS DO GOOGLE SEARCH CONSOLE (últimos 28 dias):
    {gsc_text}

    Tarefas:
    1. Lista 10 palavras-chave principais (inclui long-tail) para este nicho em Portugal, em tabela (keyword, intenção, prioridade 1-3).
    2. Sugere um novo título (máx. 60 caracteres) e uma nova meta description (máx. 155 caracteres) otimizados para CTR.
    3. Indica pelo menos 5 melhorias de conteúdo e estrutura on-page (H1/H2, secções, CTAs, internal links).
    4. Sugere 3 ideias de novas páginas / artigos que fariam sentido para este projeto (títulos sugestivos).

    Responde em português de Portugal, bem organizado em secções.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return response.choices[0].message.content

# ----- UI PRINCIPAL -----
col1, col2 = st.columns(2)
with col1:
    url = st.text_input(
        "URL da página para analisar",
        placeholder="https://teusite.pt/landing",
    )
with col2:
    niche = st.text_input(
        "Nicho / intenção",
        placeholder="ex: canalizador Lisboa, clínica dentária Sintra",
    )

st.markdown("---")

if st.button("Analisar SEO (Google + IA)"):
    if not url or not niche:
        st.error("Preenche a URL e o nicho.")
    elif not openai_key:
        st.error("Adiciona a tua OpenAI API Key na sidebar.")
    elif not gsc_property:
        st.error("Adiciona o site exato do Search Console na sidebar.")
    else:
        # 1) ligar ao GSC
        with st.spinner("A autenticar com o Google Search Console..."):
            service = get_gsc_service()

        # 2) ir buscar queries
        with st.spinner("A buscar queries do Search Console..."):
            gsc_df = fetch_gsc_queries(service, gsc_property)

        st.subheader("🔍 Queries do Google Search Console (últimos 28 dias)")
        if gsc_df.empty:
            st.warning("Sem dados no GSC (pouco tráfego ou propriedade errada).")
        else:
            st.dataframe(gsc_df)

        # 3) analisar HTML
        with st.spinner("A analisar o HTML da página..."):
            page_data = analyze_page(url)

        st.subheader("🧱 Estrutura da Página")
        st.write(f"**Title:** {page_data['title']}")
        st.write(f"**Meta description:** {page_data['meta_description']}")
        st.write(f"**H1:** {page_data['h1']}")
        st.write(f"**H2:** {page_data['h2']}")
        st.write(f"Número aproximado de palavras: {page_data['word_count']}")

        # 4) recomendações IA
        with st.spinner("A gerar recomendações com OpenAI..."):
            suggestions = get_openai_suggestions(openai_key, page_data, gsc_df, niche)

        st.subheader("🤖 Recomendações SEO (OpenAI)")
        st.write(suggestions)

st.info(
    "Esta versão é só para uso próprio: liga o teu Google, a tua OpenAI e analisa os sites que estás a criar."
)
