# AI-Driven NSE Stock Research Agent

This project analyzes NSE corporate announcements, extracts disclosure PDFs, generates Groq-backed trading signals with local Ollama fallback, conditionally validates actionable signals with Tavily, and sends Telegram alerts.

## Pipeline

```text
NSE Data -> PDF Extraction -> Groq Signal Generation -> Conditional Tavily -> Groq Validation -> Report -> Telegram Notification
```

## Project Structure

- `main.py` orchestrates the end-to-end run and writes `data/ai_research_output.json`.
- `nse_fetcher.py` fetches NSE corporate announcements, normalizes fields, fixes attachment URLs, and maintains `data/nse_master.json`.
- `graph.py` builds the LangGraph workflow.
- `state.py` defines the shared graph state.
- `nodes/` contains each pipeline step.
- `services/` wraps local Ollama calls plus external APIs for PDF extraction, Tavily, and Telegram.
- `utils/` contains logging and retry helpers.

## Environment

Create a local `.env` file:

```env
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TIMEOUT_SECONDS=90
GROQ_QUERY_TIMEOUT_SECONDS=90
GROQ_VALIDATION_TIMEOUT_SECONDS=120
OLLAMA_URL=http://localhost:11434/api/generate
LOCAL_LLM_MODELS=phi3,mistral:7b,llama3:8b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_NUM_CTX=1024
OLLAMA_NUM_PREDICT=512
OLLAMA_QUERY_TIMEOUT_SECONDS=120
OLLAMA_VALIDATION_TIMEOUT_SECONDS=240
TAVILY_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Run Ollama locally before starting the agent:

```bash
ollama pull phi3
ollama pull mistral:7b
ollama pull llama3:8b
ollama serve
```

The pipeline is intentionally sequential. Each stock completes the full chain before the next stock starts. Groq model `openai/gpt-oss-120b` is used first. If Groq fails, Ollama models are tried one at a time in this order: `phi3`, `mistral:7b`, then `llama3:8b`. Tavily is called only when the initial signal is `BUY` or `SELL`; `NEUTRAL` signals skip external search completely.

## Run

```bash
python main.py
```

By default, the system runs continuously. It processes one pending stock at a time from local `data/nse_master.json`, skips announcements already present in `data/ai_research_output.json`, prints the signal in the terminal, sends a Telegram message, saves the result, and immediately moves to the next pending stock.

The NSE website is not hit between local stock analyses. When there are no pending local announcements, the app waits a random 5-10 minutes, such as `7:31` or `8:09`, then checks NSE once for fresh announcements.

Useful options:

```bash
python main.py --once
```

Press `Ctrl+C` to stop the continuous loop.
