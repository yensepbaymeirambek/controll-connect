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

    ## How it works

    Records are pulled from MCP servers, normalized into one shape, and every
    number on screen is computed from them in `backend/app/analytics.py`. There
    are no placeholder figures: with nothing configured the dashboard shows
    zeros and says so.

    Chat and dashboards are the same endpoint. The model answers in prose and
    may propose *card specs* saying what to filter, group and count. It never
    emits figures itself — the backend executes the spec against real records,
    so a card cannot show data that is not in the workspace. Invalid specs
    (unknown card kind, unknown group_by) are dropped.

    ## Jira over MCP

    The Jira connector is an MCP client, so any server exposing a JQL search
    tool works. Point `JIRA_MCP_URL` at it and set `JIRA_MCP_TOOL` if the tool
    is not called `jira_search`.

    With credentials, run the bundled mcp-atlassian server:

    ```bash
    # fill JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN in .env first
    JIRA_MCP_URL=http://jira-mcp:9000/mcp docker compose --profile jira up --build
    ```

    Without credentials, run against the bundled stand-in, which serves
    generated issues over the same protocol:

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
    ```

    Issue fields are read from either the flat or the nested (`fields.*`) shape,
    since MCP servers differ. Jira's `statusCategory` drives the todo /
    in_progress / done split, falling back to status-name matching.

    If a source fails, the last good snapshot keeps being served and the failure
    is reported in `/api/metrics` `errors` and shown as a banner, rather than
    blanking the dashboard.

    ## ChatGPT

    Chat and card generation need a key:

    ```bash
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4o-mini      # any chat-completions model
    OPENAI_BASE_URL=              # optional OpenAI-compatible gateway
    ```

    Without a key the dashboard still works from connector data; only chat is
    disabled. Model failures come back as HTTP 200 with `mode: "error"` and a
    readable message rather than a 500.

    ## Tests

    Playwright smoke tests run against a running stack:

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
    npm run test:e2e
    ```

    ## MCP

    The VS Code MCP entry point is in `.vscode/mcp.json`. Its stdio server exposes the same workspace query surface for AI clients.
