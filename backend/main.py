"""
Personal AI News Aggregator — FastAPI Backend
=============================================
File    : main.py
Run     : uvicorn main:app --reload --port 8000

Requires environment variable:
    OPENAI_API_KEY=sk-...

Install dependencies:
    pip install fastapi uvicorn langchain langchain-openai langchain-chroma \
                chromadb openai python-dotenv
"""

import os
import logging
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate

import requests

load_dotenv()  # picks up .env file if present

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
CHROMA_PERSIST_DIR: str = "./chroma_news_db"
COLLECTION_NAME: str = "tech_news"
EMBEDDING_MODEL: str = "text-embedding-3-small"
CHAT_MODEL: str = "gpt-4o-mini"        # fast, cheap, excellent for summarisation
CHUNK_SIZE: int = 512
CHUNK_OVERLAP: int = 64
TOP_K_CHUNKS: int = 5                  # how many chunks to retrieve for context

SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a senior technology analyst. Your job is to produce concise, "
            "accurate summaries of technical news for a busy engineering audience. "
            "Never fabricate facts. If the context is insufficient, say so."
        ),
    ),
    (
        "human",
        (
            "Using ONLY the context passages below, write a summary of exactly "
            "3 sentences about: {topic}\n\n"
            "Each sentence should cover a distinct aspect (e.g., recent milestone, "
            "technical detail, industry implication). Be specific and cite key numbers.\n\n"
            "CONTEXT:\n{context}"
        ),
    ),
])

NEWS_API_KEY: str = os.environ.get("NEWS_API_KEY", "")
NEWSAPI_URL: str = "https://newsapi.org/v2/everything"

def fetch_daily_news(topic: str) -> list[dict[str, str]]:
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY is not set.")

    response = requests.get(NEWSAPI_URL, params={
        "q": topic,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY,
    })
    response.raise_for_status()
    articles = response.json().get("articles", [])

    if not articles:
        raise HTTPException(status_code=404, detail=f"No news found for topic: {topic}")

    return [
        {
            "title": a.get("title", "No title"),
            "url": a.get("url", ""),
            "content": (
                f"{a.get('title', '')}. "
                f"{a.get('description', '')} "
                f"{a.get('content', '')}"
            ),
        }
        for a in articles
        if a.get("title") and a.get("url")
    ]


# ---------------------------------------------------------------------------
# Vector store — built lazily, cached per process lifetime
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model="nomic-embed-text")


def ingest_and_get_store(topic: str) -> Chroma:
    """
    Fetch articles for `topic`, chunk them, embed, and upsert into ChromaDB.
    Returns the live Chroma instance.

    Calling this on every request is safe because ChromaDB upserts are
    idempotent when deterministic IDs are used (uuid5 from url+chunk_index).
    For production, move ingestion to a nightly cron job and open the store
    read-only here.
    """
    import uuid

    articles = fetch_daily_news(topic)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    texts, metadatas, ids = [], [], []
    for article in articles:
        chunks = splitter.split_text(article["content"])
        for idx, chunk in enumerate(chunks):
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{article['url']}#chunk-{idx}"))
            texts.append(chunk)
            metadatas.append({"title": article["title"], "url": article["url"]})
            ids.append(cid)

    store = Chroma.from_texts(
        texts=texts,
        embedding=_get_embeddings(),
        metadatas=metadatas,
        ids=ids,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    log.info("Upserted %d chunks for topic '%s'.", len(texts), topic)
    return store


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI News Aggregator API",
    description="Retrieval-augmented daily tech news summarisation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------
class SummaryResponse(BaseModel):
    topic: str
    summary: str
    sources: list[dict[str, str]]   # [{title, url}, ...]
    chunks_retrieved: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/summary", response_model=SummaryResponse)
async def get_summary(
    topic: str = Query(
        ...,
        min_length=2,
        max_length=120,
        description="The technical topic to summarise (e.g. '6G networks').",
        examples=["6G networks"],
    )
) -> SummaryResponse:
    """
    Retrieve relevant chunks from ChromaDB for `topic`, pass them to GPT-4o-mini
    via a structured prompt, and return a 3-sentence summary with source links.
    """
    log.info("Summary requested for topic: '%s'", topic)

    try:
        # 1. Ingest / refresh ChromaDB for this topic
        store = ingest_and_get_store(topic)

        # 2. Retrieve the most relevant chunks
        results: list[Document] = store.similarity_search(topic, k=TOP_K_CHUNKS)

        if not results:
            raise HTTPException(status_code=404, detail=f"No indexed content found for topic: {topic}")

        # 3. Build context string and de-duplicate sources
        context = "\n\n---\n\n".join(doc.page_content for doc in results)
        seen_urls: set[str] = set()
        sources: list[dict[str, str]] = []
        for doc in results:
            url = doc.metadata.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({"title": doc.metadata.get("title", url), "url": url})

        # 4. Call the LLM
        llm = ChatOllama(
            model="llama3.1",
            temperature=0.3,
        )
        chain = SUMMARY_PROMPT | llm
        response = await chain.ainvoke({"topic": topic, "context": context})
        summary_text: str = response.content.strip()

        log.info("Summary generated. Chunks used: %d, Sources: %d", len(results), len(sources))

        return SummaryResponse(
            topic=topic,
            summary=summary_text,
            sources=sources,
            chunks_retrieved=len(results),
        )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Pipeline error for topic '%s': %s", topic, exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(exc)}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}