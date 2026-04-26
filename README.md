# AI-Driven NSE Stock Research Agent

This project analyzes NSE corporate announcements, enriches them with PDF disclosures, web search context, market data, and local LLM reasoning, then writes analyst-style reports for each stock.

## Pipeline

```text
NSE Announcement -> Mistral Query -> PDF -> Tavily Search -> Kite Market -> Llama Reason -> Report
```

## Project Structure

- `main.py` orchestrates the end-to-end run and writes `data/ai_research_output.json`.
- `nse_fetcher.py` fetches NSE corporate announcements, normalizes fields, fixes attachment URLs, and maintains `data/nse_master.json`.
- `graph.py` builds the LangGraph workflow.
- `state.py` defines the shared graph state.
- `nodes/` contains each pipeline step.
- `services/` wraps local Ollama calls plus external APIs for PDF extraction, Tavily, and Kite.
- `utils/` contains logging and retry helpers.

## Environment

Create a local `.env` file:

```env
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_QUERY_MODEL=mistral:7b-instruct
OLLAMA_REASONING_MODEL=llama3:8b-instruct
OLLAMA_QUERY_TIMEOUT_SECONDS=90
OLLAMA_REASONING_TIMEOUT_SECONDS=240
TAVILY_API_KEY=
KITE_API_KEY=
KITE_ACCESS_TOKEN=
```

Run Ollama locally before starting the agent:

```bash
ollama pull mistral:7b-instruct
ollama pull llama3:8b-instruct
ollama serve
```

The pipeline is intentionally sequential. Each stock completes the full chain before the next stock starts, and only one local model is invoked at a time: Mistral first for fast query generation, then Llama 3 8B for deeper reasoning.

## Run

```bash
python main.py
```

By default, the system runs continuously. It processes one pending stock at a time from local `data/nse_master.json`, skips announcements already present in `data/ai_research_output.json`, prints the recommendation in the terminal, saves it, and immediately moves to the next pending stock.

The NSE website is not hit between local stock analyses. When there are no pending local announcements, the app waits a random 5-10 minutes, such as `7:31` or `8:09`, then checks NSE once for fresh announcements.

Useful options:

```bash
python main.py --once
```

Press `Ctrl+C` to stop the continuous loop.
