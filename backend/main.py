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
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate

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

# ---------------------------------------------------------------------------
# Mock news source  (identical contract to Phase 1 — swap for real API later)
# ---------------------------------------------------------------------------
def fetch_daily_news(topic: str) -> list[dict[str, str]]:
    return [
        {
            "title": f"{topic} — Terahertz Spectrum Trials Hit 1 Tbps Milestone",
            "url": f"https://techcrunch.example.com/{topic.replace(' ', '-')}-tbps-milestone",
            "content": (
                f"Researchers at the Global Wireless Institute announced this week that "
                f"laboratory trials for {topic} networks have surpassed the 1 Tbps threshold "
                f"for the first time using sub-terahertz spectrum bands between 100 GHz and "
                f"300 GHz. The experiment used a 1024-element massive MIMO antenna array paired "
                f"with AI-driven beamforming. Adaptive phase-coherence compensation eliminated "
                f"atmospheric absorption losses that previously capped speeds at ~400 Gbps. "
                f"Outdoor pilots are expected in Tokyo and Helsinki by Q3 2026."
            ),
        },
        {
            "title": f"{topic} Standard Freeze: 3GPP Release 21 Roadmap Leaked",
            "url": f"https://lightreading.example.com/3gpp-release-21-{topic.lower().replace(' ', '-')}",
            "content": (
                f"A 3GPP working-group document reveals Release 21—the {topic} baseline—targets "
                f"a Stage 3 Freeze in late 2029. Key features include AI/ML layer-2 scheduling, "
                f"ISAC waveforms, NTN multi-orbit handover, and the NR-X air interface above "
                f"100 GHz. Latency targets are sub-100 microseconds for URLLC slices—10x tighter "
                f"than 5G NR. Qualcomm and Ericsson have filed over 1,200 essential patent claims."
            ),
        },
        {
            "title": f"AI-Native {topic}: How On-Device Intelligence Changes Radio Access",
            "url": f"https://ieee.example.com/spectrum/{topic.replace(' ', '')}-ai-native-ran",
            "content": (
                f"{topic} embeds ML directly into the RAN stack. A joint MIT/Samsung paper "
                f"proposes a RL scheduler operating at the physical layer with a 3 ms lookahead "
                f"window. In urban canyon simulations it reduced packet retransmissions by 38% "
                f"and improved spectral efficiency by 2.4 bps/Hz. The neural net runs on a "
                f"dedicated NPU consuming under 800 mW."
            ),
        },
        {
            "title": f"{topic} and the Environment: Energy Per Bit Targets Revisited",
            "url": f"https://greennetworks.example.com/{topic.lower().replace(' ', '-')}-sustainability",
            "content": (
                f"The GSMA Net Zero 2050 pledge targets 1 picojoule/bit at the {topic} access "
                f"node—100x better than today's 5G base stations. Liquid-cooled mMIMO panels, "
                f"GaN amplifiers at 70% efficiency, and dynamic spectrum sharing with Wi-Fi 8 "
                f"could cut idle-mode power by 45%. Mandatory EU energy-efficiency labelling "
                f"for {topic} base stations may follow from 2030."
            ),
        },
        {
            "title": f"Spectrum Wars: Who Owns the {topic} Frontier Bands?",
            "url": f"https://policy.example.com/spectrum-{topic.lower().replace(' ', '-')}",
            "content": (
                f"WRC-27 will vote on {topic} candidate bands above 92 GHz. The US/Japan bloc "
                f"favours shared-access D-band (130–174.8 GHz); China/EU prefer exclusive "
                f"licensed blocks. Satellite operators are lobbying to protect Ka/V-band from "
                f"adjacent {topic} uplink interference. A fragmented spectrum map could delay "
                f"roaming agreements by 5+ years."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Vector store — built lazily, cached per process lifetime
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _get_embeddings() -> OpenAIEmbeddings:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)


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
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured on the server.")

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
        llm = ChatOpenAI(
            model=CHAT_MODEL,
            temperature=0.3,        # low temp → factual, reproducible
            openai_api_key=OPENAI_API_KEY,
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