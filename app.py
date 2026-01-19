import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
st.set_page_config(page_title="SEO Otimizator PT", page_icon="🧠", layout="wide")
st.title("🧠 SEO Otimizator PT")

# SECRETS (Streamlit Cloud)
OPENAI_KEY = st.secrets["OPENAI_KEY"]  # <- AQUI! Usa a key dos secrets
client = OpenAI(api_key=OPENAI_KEY)

st.markdown("Analisa sites com OpenAI + Google Search Console")

# Sidebar limpa
st.sidebar.header("Config")
gsc_property = st.sidebar.text_input("URL GSC", value="https://teusite.pt/")
st.sidebar.success("✅ OpenAI ativa")

# GSC service (secrets)
def get_gsc_service():
    client_config = {
        "installed": {
            "client_id": st.secrets.get("GSC_CLIENT_ID", ""),
            "client_secret": st.secrets.get("GSC_CLIENT_SECRET", ""),
            "redirect_uris": ["http://localhost"]
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    return build("searchconsole", "v1", credentials=creds)

def fetch_gsc_queries(service, site_url, days=28):
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)
    request = {"startDate": str(start_date), "endDate": str(end_date), "dimensions": ["QUERY"], "rowLimit": 100}
    response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
    rows = response.get("rows", [])
    data = [{"query": r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions
