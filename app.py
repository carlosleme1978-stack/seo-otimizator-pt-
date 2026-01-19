import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ----- CONFIG -----
st.set_page_config(page_title="SEO Otimizator - OpenAI", page_icon="🧠", layout="wide")
st.title("🧠 SEO Otimizator (OpenAI Only)")
st.markdown("Analisa a página e gera recomendações SEO usando OpenAI (sem Google Search Console)")

# ----- SECRETS -----
openai_key = st.secrets.get("OPENAI_API_KEY")
if not openai_key:
    st.error("OPENAI_API_KEY não configurada nos Secrets do Streamlit.")

# ----- FUNÇÃO: ANALISAR PÁGINA -----
def analyze_page(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    
    from bs4 import BeautifulSoup
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

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "h2": h2,
        "word_count": len(text.split()),
        "raw_text": text[:4000],
    }

# ----- FUNÇÃO: RECOMENDAÇÕES OPENAI -----
def get_openai_suggestions(openai_key, page_data, niche):
    client = OpenAI(api_key=openai_key)

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

Tarefas:
1. Lista 10 keywords prioritárias (tabela).
2. Sugere novo title (≤60 chars) e meta description (≤155).
3. Indica melhorias on-page (conteúdo + estrutura).
4. Sugere 3 novas páginas/artigos estratégicos.

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
    else:
        try:
            with st.spinner("A analisar HTML..."):
                page_data = analyze_page(url)

            with st.spinner("🤖 A gerar recomendações SEO..."):
                suggestions = get_openai_suggestions(openai_key, page_data, niche)

            st.subheader("📈 Recomendações SEO (OpenAI)")
            st.write(suggestions)

        except Exception as e:
            st.error("Erro durante a análise.")
            st.exception(e)

st.info("Versão simplificada: apenas OpenAI, sem Google Search Console.")
