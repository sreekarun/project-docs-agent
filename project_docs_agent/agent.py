"""Project docs agent: answers questions about the adk-chatbot project from its docs.

Answers come only from the bundled docs snapshot (project_docs_agent/docs/,
refreshed with scripts/sync_docs.sh), with the doc and section cited.
"""

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from project_docs_agent import docs_index

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.8-flash")
# gemini-3.8-flash is only served from `global`, while Agent Runtime sets
# GOOGLE_CLOUD_LOCATION to its region, so model calls get their own location.
MODEL_LOCATION = os.getenv("MODEL_LOCATION", "global")

_MAX_SECTION_CHARS = 6000


def list_docs() -> dict:
    """List the project docs and their section headings.

    Returns:
        A dict with status and, per doc, its file name and section headings.
    """
    docs: dict[str, list[str]] = {}
    for s in docs_index.sections():
        docs.setdefault(s.doc, []).append(s.heading)
    return {
        "status": "success",
        "docs": [{"doc": d, "sections": h} for d, h in docs.items()],
    }


def search_docs(query: str) -> dict:
    """Search the project docs for sections relevant to a question.

    Args:
        query: Keywords from the question, e.g. "agent identity switch runtime".

    Returns:
        A dict with status and the best-matching sections (doc, heading, excerpt).
    """
    hits = docs_index.search(query)
    if not hits:
        return {"status": "no_results", "query": query}
    return {
        "status": "success",
        "results": [
            {"doc": s.doc, "heading": s.heading, "excerpt": s.text[:1500]}
            for _, s in hits
        ],
    }


def read_doc_section(doc: str, heading: str) -> dict:
    """Read one full section of a project doc.

    Args:
        doc: The doc file name from search_docs or list_docs, e.g. "operations.md".
        heading: The section heading, exactly as returned by search_docs or list_docs.

    Returns:
        A dict with status and the section text.
    """
    for s in docs_index.sections():
        if s.doc == doc and s.heading == heading:
            return {
                "status": "success",
                "doc": doc,
                "heading": heading,
                "text": s.text[:_MAX_SECTION_CHARS],
            }
    return {"status": "not_found", "doc": doc, "heading": heading}


root_agent = Agent(
    # Keep in sync with create_params.root_agent_name in agents-cli-manifest.yaml.
    # It's also the agent card's name, which is how Agent Registry lists this agent.
    name="project_docs_agent",
    model=Gemini(
        model=MODEL_NAME,
        client_kwargs={"location": MODEL_LOCATION},
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description=(
        "Answers questions about the adk-chatbot project (architecture, CI/CD, "
        "deployment, operations, troubleshooting, Agent Identity, history) from "
        "its documentation, citing the doc and section."
    ),
    instruction="""You answer questions about the adk-chatbot project: its architecture,
CI/CD pipeline, deployment and release process, operations, troubleshooting, Agent
Identity, and the history of how it was built.

How to work:
1. Call search_docs with the key terms of the question. Try a second query with
   different terms if the first results don't answer it.
2. Call read_doc_section for the most relevant sections when the excerpt is cut
   off or you need the details.
3. Use list_docs when the user asks what documentation exists.

Rules:
- Answer only from the docs. If they don't cover the question, say so plainly
  and name the closest doc that might help. Never invent commands, flags,
  resource names or steps.
- Quote commands exactly as they appear in the docs.
- End with the sources you used, e.g. "Source: operations.md, Switching a
  runtime to Agent Identity".""",
    tools=[list_docs, search_docs, read_doc_section],
)

app = App(
    root_agent=root_agent,
    name="project_docs_agent",
)
