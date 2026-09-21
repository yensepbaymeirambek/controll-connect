# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    # Signal workspace

    AI workspace for querying and visualizing work data from Jira, Asana, Linear, and future connectors.

    ## Run with Docker

    Both services share the `connector-net` bridge network, so containers reach
    each other by service name (`http://backend:8000`).

    Dev (vite HMR + `uvicorn --reload`, source bind-mounted):

    ```bash
    docker compose up --build
    ```

    - frontend: http://localhost:5173 (proxies `/api` and `/health` to `backend:8000`)
    - backend: http://localhost:8000

    Production (nginx serves the built bundle and reverse-proxies `/api`):

    ```bash
    docker compose -f docker-compose.prod.yml up --build -d
    ```

    - app: http://localhost:8080 — backend is not published to the host, only
      reachable inside `connector-net`.

    The browser cannot resolve `backend` itself, so frontend requests go to
    relative paths (`/api/...`); the vite proxy in dev and nginx in prod forward
    them to the backend by name. `.env` is loaded if present.

    ## Run frontend

    ```bash
    npm run dev
    ```

    ## Run backend

    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000
    ```

    The API starts in local mock mode. Copy `.env.example` to `.env` and add provider credentials before implementing live sync adapters. The connector boundary lives in `backend/app/connectors/`; each adapter should implement `Connector` and normalize records to a common shape.

    ## ChatGPT

    `/api/query` is answered by ChatGPT. Set the key in `.env`:

    ```bash
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4o-mini      # any chat-completions model
    OPENAI_BASE_URL=              # optional OpenAI-compatible gateway
    ```

    Without a key the endpoint stays in local mode and returns a canned answer,
    so the app runs unconfigured. The response carries a `mode` field: `llm`,
    `local`, or `error` when the model call failed.

    The model only sees records returned by the connector registry in
    `backend/app/connectors/registry.py`, and is instructed not to invent work
    items that are absent from them. Model failures come back as HTTP 200 with
    `mode: "error"` and a readable message rather than a 500.

    ## MCP

    The VS Code MCP entry point is in `.vscode/mcp.json`. Its stdio server exposes the same workspace query surface for AI clients.
