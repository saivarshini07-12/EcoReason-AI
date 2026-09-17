# EcoReason.AI

EcoReason.AI is an inspectable biodiversity intelligence prototype for the Darukaa.Earth challenge. It combines a structured SQLite knowledge layer, transparent retrieval, multi-metric reasoning, and session memory in a small Python HTTP API. It is deliberately usable without an API key: a hosted LLM can be added later as a response-writing layer, but scientific evidence selection remains inspectable.

## Architecture

```text
text or JSON metrics -> session context -> clarification gate
																			-> lexical retrieval from SQLite
																			-> multi-metric recommendation rules
																			-> action / mechanism / metrics / horizon / confidence / sources
```

`eco-reason-ai/data/knowledge.json` is the source dataset. On first start it is loaded into `data/knowledge.sqlite3`, whose `sources` table stores publisher, year, URL, tags, evidence, and guidance. Retrieval scores token overlap across those fields and returns the source IDs used by each recommendation. This is a small RAG-like baseline with a clear upgrade path to embeddings or a vector database.

The seeded sources are FAO land and agroecology reports, the IPBES Global Assessment, and IPCC AR6 WGII. Claims are intentionally framed as measurable targets and monitoring plans rather than fabricated universal percentage effects.

## Run locally

```bash
cd eco-reason-ai
python3 app.py
```

The API listens at `http://127.0.0.1:8000`.

### Streamlit app with local Gemma 3 1B

Install the UI dependency and start both processes in separate terminals:

```bash
pip install -r requirements.txt
python app.py
streamlit run frontend/app.py
```

In LM Studio, load `Gemma 3 1B`, start the local server on `http://127.0.0.1:1234`, and keep the OpenAI-compatible API enabled. The Streamlit toggle sends the grounded assessment to `/v1/chat/completions`; if LM Studio is offline, the structured evidence-backed response still renders. Use `LM_STUDIO_MODEL` if the model identifier shown by LM Studio differs from `gemma-3-1b`.

### Text conversation

```bash
curl -s http://127.0.0.1:8000/chat \
	-H 'Content-Type: application/json' \
	-d '{"session_id":"demo","message":"Biodiversity is declining on my land"}'
```

The first response asks for missing soil organic carbon, rainfall, and land-use data. Continue the same `session_id` or send structured metrics:

```bash
curl -s http://127.0.0.1:8000/chat \
	-H 'Content-Type: application/json' \
	-d '{"session_id":"demo","message":"Please assess my semi-arid farm", "metrics":{"soil_organic_carbon":0.3,"rainfall":"low","land_use":"monoculture wheat","region":"semi-arid"}}'
```

Other endpoints: `GET /health` and `GET /sources`.

## Output contract

Complete responses contain the resolved context, two recommendations, impacted metrics, scientific mechanism, expected measurement/change, time horizon, confidence, evidence IDs, and the retrieved source records. The recommendation deliberately connects at least three variables: soil carbon and moisture, land use and connectivity, and rainfall/temperature exposure.

## Test

```bash
python3 -m unittest -v
```

## Database and CI/CD

The service has no third-party runtime dependency, so it can run on a minimal Python container or platform-as-a-service. A CI job should run `python3 -m unittest -v` on Python 3.11-3.14 and fail on test errors. For deployment, expose port 8000 behind a TLS reverse proxy and persist `data/knowledge.sqlite3`; rebuild that file whenever the reviewed source dataset changes. No credentials are required for the local demo.

## Submission links

- GitHub repository: add the final repository URL here before submitting the Word document.
- Live demo: add the deployed URL here if deployed.
- Review notes: `GET /sources` makes the knowledge layer and cited source metadata directly inspectable.