# Travel Companion Agent

A Next.js interface with a Python/FastAPI backend for a budget-aware travel research companion.

## Architecture

- `app/` contains the React/Next.js interface.
- `app/api/chat/route.ts` is a thin same-origin proxy. It never contains the agent logic or browser-visible secrets.
- `backend/app.py` exposes the FastAPI streaming endpoint.
- `backend/agent.py` contains the agentic loop: guardrail, planning, search, source triage, evaluation, stopping rules, and final answer.
- `backend/services.py` contains the OpenAI, Tavily, page-fetching, token, and cost helpers.
- `backend/models.py` contains the typed Pydantic data models.

## What It Does

The user describes a trip. The agent:

1. Checks that the request is about travel recommendations.
2. Plans a research strategy from the user's dates, budget, pace, interests, and constraints.
3. Uses a mini-model input guardrail to separate intended destinations from comparison examples and explicit source-language preferences.
4. Asks whether local-language sources would meaningfully improve the answer.
5. Searches wide with 10 snippet-sized results per query.
6. Uses a cheaper triage model to read snippets and pick only 2-3 pages to fetch.
7. Fetches narrow, evaluates evidence, and decides whether to search more or recommend.
8. Stops early when 3 destinations each meet 4 user criteria.
9. Returns 2-5 recommendations and logs token/cost usage for the session.

## Cost Discipline

The defaults are set in `backend/config.py`:

- 5 candidate destinations max
- 10 full web fetches max
- 5 searches max
- 10 snippets per search
- 3 fetched pages per search
- `gpt-4.1-mini` for the input guardrail and research plan
- `gpt-4.1-nano` for snippet triage and candidate evaluation
- `gpt-4.1-mini` for the final streamed answer

The target average is about `$0.30` per run, with a hard design ceiling of `$1.00`. The loop reserves room for the final answer, stops when the estimated ceiling is reached, limits final output, and bounds conversation input size. Set `WEB_SEARCH_COST_PER_CALL_USD` to your provider's effective search cost so it is included in the session estimate.

Actual billing still depends on current model and search-provider pricing. Use project-level spending limits as the final enforcement layer.

## Local Setup

```bash
pnpm install
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Add:

- `OPENAI_API_KEY`
- `TAVILY_API_KEY`

Optional model overrides include `OPENAI_GUARDRAIL_MODEL`, `OPENAI_TRIAGE_MODEL`, and `OPENAI_ANSWER_MODEL`.

Start the Python agent in one terminal:

```bash
pnpm dev:agent
```

Start Next.js in a second terminal:

```bash
pnpm dev
```

Then open [http://localhost:3000](http://localhost:3000). The browser calls Next.js, and Next.js privately proxies to `http://127.0.0.1:8000`.

## Tests

```bash
.venv/bin/python -m unittest discover -s backend/tests
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

## Deployment

The frontend and Python API are now separate services:

1. Deploy `backend/` to a Python host such as Render, Railway, Fly.io, or Google Cloud Run using:
   `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
2. Add `OPENAI_API_KEY`, `TAVILY_API_KEY`, and optional model controls to the Python service.
3. Deploy the Next.js app to Vercel.
4. Set Vercel's server-only `PYTHON_AGENT_URL` to the public URL of the Python service.

Do not prefix `PYTHON_AGENT_URL` or either API key with `NEXT_PUBLIC_`; those variables must remain server-only.
