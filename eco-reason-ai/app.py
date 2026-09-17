"""EcoReason.AI: inspectable biodiversity reasoning service."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lm_studio import generate_answer

ROOT = Path(__file__).parent
KNOWLEDGE_PATH = ROOT / "data" / "knowledge.json"
DB_PATH = ROOT / "data" / "knowledge.sqlite3"


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


@dataclass
class Message:
    role: str
    content: str


class KnowledgeStore:
    """SQLite-backed knowledge layer with transparent lexical retrieval."""

    def __init__(self, database: Path | str = DB_PATH) -> None:
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, publisher TEXT NOT NULL,
            year INTEGER, url TEXT NOT NULL, tags TEXT NOT NULL,
            evidence TEXT NOT NULL, guidance TEXT NOT NULL
        )""")
        self._seed()

    def _seed(self) -> None:
        if self.connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]:
            return
        records = json.loads(KNOWLEDGE_PATH.read_text())
        self.connection.executemany("INSERT INTO sources VALUES (:id, :title, :publisher, :year, :url, :tags, :evidence, :guidance)", records)
        self.connection.commit()

    def search(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        query_terms = tokens(query)
        ranked: list[tuple[int, dict[str, Any]]] = []
        for row in self.connection.execute("SELECT * FROM sources"):
            searchable = tokens(" ".join(str(row[key]) for key in ("title", "publisher", "tags", "evidence", "guidance")))
            score = len(query_terms & searchable)
            if score:
                item = dict(row)
                item["tags"] = json.loads(item["tags"])
                ranked.append((score, item))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked[:limit]]


class Conversation:
    required = ("soil_organic_carbon", "rainfall", "land_use")

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store
        self.messages: list[Message] = []
        self.context: dict[str, Any] = {}

    def _extract(self, text: str, structured: dict[str, Any] | None) -> None:
        if structured:
            self.context.update({key: value for key, value in structured.items() if value not in (None, "")})
        patterns = {
            "soil_organic_carbon": r"(?:soil organic carbon|organic carbon|soc)\s*(?:is|:)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",
            "soil_ph": r"(?:soil )?ph\s*(?:is|:)?\s*([0-9]+(?:\.[0-9]+)?)",
            "rainfall": r"rainfall\s*(?:is|:)?\s*([a-z-]+|[0-9]+(?:\.[0-9]+)?\s*(?:mm|mm/year)?)",
            "temperature": r"temperature\s*(?:is|:)?\s*([0-9]+(?:\.[0-9]+)?\s*°?c?)",
            "land_use": r"(?:land use|crop|farming)\s*(?:is|:)?\s*([a-z -]+?)(?:,|\.|\s+region|$)",
            "region": r"region\s*(?:is|:)?\s*([a-z -]+?)(?:,|\.|$)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match and key not in self.context:
                self.context[key] = match.group(1).strip()

    def _missing(self) -> list[str]:
        return [key for key in self.required if key not in self.context]

    def respond(self, text: str, structured: dict[str, Any] | None = None, use_local_llm: bool = False) -> dict[str, Any]:
        self._extract(text, structured)
        self.messages.append(Message("user", text))
        missing = self._missing()
        if missing:
            labels = {"soil_organic_carbon": "soil organic carbon (%)", "rainfall": "rainfall pattern", "land_use": "land use or crop"}
            question = "To reason across soil, water, and habitat, please provide " + ", ".join(labels[key] for key in missing) + "."
            answer = {"status": "needs_clarification", "question": question, "missing": missing, "context": self.context, "retrieved_evidence": []}
            self.messages.append(Message("assistant", question))
            return answer
        query = " ".join(str(value) for value in self.context.values()) + " biodiversity soil water habitat pollinator carbon"
        evidence = self.store.search(query)
        answer = {"status": "complete", "context": self.context, "recommendations": self._recommend(evidence), "retrieved_evidence": [{key: source[key] for key in ("id", "title", "publisher", "year", "url", "evidence")} for source in evidence], "conversation_turns": len(self.messages)}
        if use_local_llm:
            answer["llm_answer"] = generate_answer(answer)
        self.messages.append(Message("assistant", json.dumps(answer)))
        return answer

    def _recommend(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        low_carbon = float(self.context.get("soil_organic_carbon", 99)) < 1
        dry = any(word in str(self.context.get("rainfall", "")).lower() for word in ("low", "dry", "arid", "drought"))
        sources = evidence[:2]
        return [
            {"action": "Replace bare fallow with a drought-tolerant legume-grass cover-crop mix and retain residues.", "why_it_works": "Living roots add carbon inputs and reduce erosion; legumes supply biologically fixed nitrogen. Greater soil structure and moisture retention support decomposers and a wider food web, linking soil recovery to above-ground habitat.", "impacted_metrics": ["soil organic carbon", "soil moisture", "microbial diversity", "pollinator habitat"], "expected_change": "Target a measurable upward soil-carbon trend over 2-3 years; verify with annual 0-15 cm soil tests and vegetation surveys rather than assuming a fixed percentage.", "time_horizon": "short: establish cover; medium: soil carbon and habitat response", "confidence": "high" if low_carbon else "medium", "evidence_ids": [source["id"] for source in sources]},
            {"action": "Add two or more native tree/shrub strips along field edges or drainage lines, while keeping a connected corridor between patches.", "why_it_works": "A connected, layered habitat reduces fragmentation and provides shade, nesting sites, and refuge during heat or dry periods. Rooted strips also slow runoff, so water availability and habitat diversity improve together without converting the whole field.", "impacted_metrics": ["habitat diversity", "species richness", "runoff", "water availability", "temperature exposure"], "expected_change": "Measure habitat structure and indicator species seasonally; structural benefits begin in 1-2 years and woody habitat benefits compound over 5+ years.", "time_horizon": "medium: habitat structure; long: species richness and connectivity", "confidence": "high" if dry else "medium", "evidence_ids": [source["id"] for source in evidence[1:3]]},
        ]


class Handler(BaseHTTPRequestHandler):
    store = KnowledgeStore()
    sessions: dict[str, Conversation] = {}

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {"service": "EcoReason.AI", "status": "ok", "knowledge_layer": "sqlite + lexical retrieval"})
        elif path == "/":
            self._json(200, {"service": "EcoReason.AI", "streamlit": "Run `streamlit run frontend/app.py`", "chat": "POST /chat", "sources": "GET /sources"})
        elif path == "/sources":
            self._json(200, {"sources": self.store.search("soil biodiversity climate land water", limit=100)})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/chat":
            self._json(404, {"error": "Not found"})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            session_id = payload.get("session_id", "default")
            message = payload.get("message", "")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("message must be a non-empty string")
            conversation = self.sessions.setdefault(session_id, Conversation(self.store))
            self._json(200, conversation.respond(message, payload.get("metrics"), payload.get("use_local_llm", False)))
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("EcoReason.AI listening on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()