# 📰 AI News Aggregator

![Vue.js](https://img.shields.io/badge/Vue.js-35495E?style=flat&logo=vue.js&logoColor=4FC08D)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=FastAPI&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-121212?style=flat)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F00?style=flat)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-blue)

A full-stack **Retrieval-Augmented Generation (RAG)** application that fetches real-time tech news, indexes article chunks into a vector database, and serves concise, AI-generated summaries with source attribution.

<img width="1871" height="818" alt="Screenshot 2026-03-01 at 10 53 53 PM" src="https://github.com/user-attachments/assets/857157a9-169f-4231-965a-2785463b1d45" />

## ✨ Features
- **Live Data Ingestion:** Fetches the latest articles via NewsAPI based on user queries.
- **Local AI Processing:** Utilizes `Ollama` for both embeddings (`nomic-embed-text`) and summarization (`llama3.1`), ensuring data privacy and zero API costs for the LLM.
- **Vector Search:** Chunks and indexes documents into a local `ChromaDB` instance for semantic retrieval.
- **Reactive UI:** A clean, responsive single-page application built with Vue 3 and Vite.

## 🛠️ Tech Stack
- **Frontend:** Vue 3 (Composition API), Vite
- **Backend:** Python 3.9+, FastAPI, Uvicorn
- **AI / Data:** LangChain, ChromaDB, Ollama
- **External APIs:** NewsAPI

---

## 🚀 Getting Started

### Prerequisites
- [Node.js](https://nodejs.org/) (v18+) & npm
- [Python](https://www.python.org/) (v3.9+)
- [Ollama](https://ollama.ai/) running locally with the following models pulled:
  ```bash
  ollama run llama3.1
  ollama pull nomic-embed-text
