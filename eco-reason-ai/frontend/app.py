"""Streamlit UI for the EcoReason.AI local biodiversity assistant."""

from __future__ import annotations

import json
import os
import uuid
from urllib.error import URLError
from urllib.request import Request, urlopen

import streamlit as st


BACKEND_URL = os.getenv("ECOREASON_BACKEND_URL", "http://127.0.0.1:8000")


def post_chat(message: str, metrics: dict) -> dict:
    payload = {
        "session_id": st.session_state.session_id,
        "message": message,
        "metrics": metrics,
        "use_local_llm": st.session_state.use_local_llm,
    }
    request = Request(
        f"{BACKEND_URL}/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def render_recommendations(response: dict) -> None:
    for index, recommendation in enumerate(response.get("recommendations", []), start=1):
        st.subheader(f"Recommendation {index}: {recommendation['action']}")
        st.markdown(f"**Why it works:** {recommendation['why_it_works']}")
        st.write("**Impacted metrics:** " + ", ".join(recommendation["impacted_metrics"]))
        st.write(f"**Expected change:** {recommendation['expected_change']}")
        st.write(f"**Time horizon:** {recommendation['time_horizon']}")
        st.write(f"**Confidence:** {recommendation['confidence'].title()}")
        st.caption("Evidence IDs: " + ", ".join(recommendation["evidence_ids"]))


st.set_page_config(page_title="EcoReason.AI", page_icon="🌱", layout="wide")
st.title("EcoReason.AI")
st.caption("Evidence-grounded biodiversity intelligence with local Gemma 3 1B reasoning")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []
if "use_local_llm" not in st.session_state:
    st.session_state.use_local_llm = True

with st.sidebar:
    st.header("Environmental context")
    st.session_state.use_local_llm = st.toggle("Use LM Studio / Gemma 3 1B", value=True)
    st.caption("LM Studio must be serving an OpenAI-compatible model at 127.0.0.1:1234.")
    organic_carbon = st.number_input("Soil organic carbon (%)", min_value=0.0, max_value=20.0, value=0.3, step=0.1)
    rainfall = st.selectbox("Rainfall pattern", ["low", "seasonal", "moderate", "high", "drought-prone"])
    land_use = st.text_input("Land use or crop", value="monoculture wheat")
    soil_ph = st.number_input("Soil pH (optional)", min_value=0.0, max_value=14.0, value=7.0, step=0.1)
    region = st.text_input("Region (optional)", value="semi-arid")
    if st.button("Start new conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []
        st.rerun()

for item in st.session_state.history:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

message = st.chat_input("Describe your biodiversity or land concern")
if message:
    metrics = {
        "soil_organic_carbon": organic_carbon,
        "rainfall": rainfall,
        "land_use": land_use,
        "soil_ph": soil_ph,
        "region": region,
    }
    st.session_state.history.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.markdown(message)
    try:
        response = post_chat(message, metrics)
        with st.chat_message("assistant"):
            if response["status"] == "needs_clarification":
                st.info(response["question"])
            else:
                if response.get("llm_answer"):
                    st.markdown(response["llm_answer"])
                render_recommendations(response)
                with st.expander("Retrieved scientific evidence"):
                    for source in response.get("retrieved_evidence", []):
                        st.markdown(f"**{source['publisher']} ({source['year']})**: [{source['title']}]({source['url']})")
                        st.write(source["evidence"])
                st.session_state.history.append({"role": "assistant", "content": "Assessment complete. See the recommendations and evidence above."})
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        st.error(f"Backend unavailable at {BACKEND_URL}. Start it with `python app.py`. Details: {error}")