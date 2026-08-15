# ⚡ ASKLY Enterprise RAG & Neural Intelligence Infrastructure

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-005571?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18%2B-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.8%2B-38Bdf8?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Persistent-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

**The definitive autonomous intelligence infrastructure featuring enterprise vector search, zero-latency embeddings, semantic query rewriting, and persistent SQLite knowledge architecture.**

</div>

---

## **🚀 Overview**

**ASKLY** is a production-grade, full-stack Enterprise RAG (Retrieval-Augmented Generation) system built to ingest documents, perform advanced vector searches (ChromaDB / FAISS), execute smart query rewriting, and manage operator notes seamlessly with a modern Silicon Valley-inspired UI. ASKLY is my Internship Capstone Project in AI Engineering at Visionerds in Summers-2026, developed under the supervision of my mentor Ms. Eman Mohsin. 

---

## **🛠️ Tech Stack**

### **Backend**
* **Framework:** FastAPI (Python)
* **Vector Database & Search:** ChromaDB / FAISS
* **Database & Persistence:** SQLite (Async ORM / Native)
* **LLM Integration:** Groq / Gemini API

### **Frontend**
* **Library:** React (Vite)
* **Styling:** Tailwind CSS (Dark/Light Silicon Valley Theme)
* **Interactivity:** Command Palette (`⌘K`), Live Telemetry HUD, Real-time Notes Vault

---

## **📂 Project Architecture**

```text
ASKLY/
├── app/                  # FastAPI Backend Modules & Routers
│   ├── api/              # Endpoints (/chat, /notes, etc.)
│   ├── core/             # LLM Client & Configurations
│   └── main.py           # FastAPI Application Entrypoint
├── askly-frontend/       # React + Vite Frontend Application
│   ├── src/              # Components & App.jsx
│   └── package.json      # Frontend Dependencies
├── chroma_db/            # Vector Embeddings Storage
├── data/                 # Raw Document Vault
├── askly.db              # Persistent SQLite Database
├── requirements.txt      # Python Dependencies
└── .env                  # Environment Configuration

**Key Features:**

1. Advanced RAG Pipeline: Semantic chunking and high-speed vector retrieval.

2. Persistent SQLite Vault: Instant note recording and session-based retrieval displayed directly in the dashboard UI.

3. Command Center (⌘K): Quick operational shortcuts for navigation and queries.

4. Live Telemetry HUD: Real-time backend latency monitoring.

5. Dual Theme: Immersive Dark and Clean Light Silicon Valley UI aesthetics.

## **Architect & Lead Engineer**

Developed by: Muhammad Tayyab Malik
Supervisor: Ms. Eman Mohsin 