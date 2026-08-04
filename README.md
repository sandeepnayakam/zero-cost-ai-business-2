# Zero-Cost AI Business — v3 (Agentic Loop)

An autonomous AI agent that runs every 30 minutes on GitHub Actions (free), with a multi-step agentic loop, daily budget management across 7 free LLM providers, and a built-in experiment-driven methodology. It builds useful web tools and content on a GitHub Pages site (also free), and monetizes them through crypto tips and other zero-cost revenue tracks.

## What Makes v3 Different

| Feature | v2 | v3 (this version) |
|---------|----|--------------------|
| Run frequency | Every 2 hours | Every 30 minutes |
| Actions per run | 1 | 1-5 (multi-step agentic loop) |
| LLM budget | Unlimited (could exhaust) | Daily budget tracking per provider |
| Budget pacing | None | Scales steps based on remaining budget |
| Tools available | 3 (write, append, http) | 8 (write, read, list, delete, append, http, log_experiment, update_experiment) |
| Prompt style | Prescriptive task lists | Minimal — agent decides what to do |
| Methodology | "Build these specific tools" | "Run small experiments. Kill what doesn't work. Double down on what does." |
| Pre-loaded tools | 4 | 8 |

## How It Works

### The Agentic Loop

Each run, the agent:
1. Reads all memory files + budget status
2. Calls the LLM with full context → gets an action
3. Executes the action (write file, read file, list dir, etc.)
4. Feeds the action result back to the LLM → gets next action
5. Repeats until: agent says "done", max steps reached, or budget exhausted

This lets the agent do **multi-step work in a single run**, e.g.:
- Read existing `docs/tools/` → identify a gap → create a new tool → verify it → log an experiment
- Check wallet balance via free API → log revenue → update the tip page → write a blog post about it
- List all docs → find broken links → fix them → log the fix

### Daily Budget Management

The agent spreads its daily LLM budget across the whole day instead of exhausting it in the first few runs.

| Budget Level | Remaining | Max Steps/Run |
|---|---|---|
| full | >80% | 5 |
| high | 50-80% | 4 |
| medium | 20-50% | 3 |
| low | 5-20% | 2 |
| critical | 1-5% | 1 |
| exhausted | 0% | skip run |

**Total daily capacity**: ~18,550 requests across all 7 providers
**Max daily usage**: 48 runs × 5 steps = 240 calls/day

So budget is plentiful — the tracker mainly prevents bursts and ensures the agent stays active all day.

### Multi-Provider LLM Fallback

The agent supports 7 free LLM providers and tries them in priority order:

1. **Groq** (GROQ_API_KEY) — 14K req/day, Llama 3.3 70B
2. **Google Gemini** (GEMINI_API_KEY) — 1,500 req/day, Gemini Flash
3. **Cerebras** (CEREBRAS_API_KEY) — 1,000 req/day
4. **SambaNova** (SAMBANOVA_API_KEY) — 500 req/day
5. **Cloudflare Workers AI** (CF_API_TOKEN + CF_ACCOUNT_ID) — 1,000 req/day
6. **HuggingFace** (HF_TOKEN) — 500 req/day
7. **OpenRouter** (OPENROUTER_API_KEY) — 50 req/day (free models)

If one provider fails or is exhausted, it automatically falls back to the next.

## Setup (10 minutes)

### Step 1: Create the GitHub repo

1. Create a new **public** repo on GitHub (e.g., `zero-cost-ai-business`).
2. Copy ALL files from this project into the repo (preserving the folder structure).
3. Commit and push to `main`.

### Step 2: Get free LLM API keys

Set up as many as you like — the agent uses them in fallback order:

| Provider | Where to get free key | Notes |
|---|---|---|
| **Groq** ⭐ | https://console.groq.com/keys | Best free option. 14K req/day. |
| **Google Gemini** ⭐ | https://aistudio.google.com/apikey | Best free quality. No card needed. |
| Cerebras | https://cloud.cerebras.ai/ | Super-fast inference |
| SambaNova | https://cloud.sambanova.ai/ | Big models (405B) |
| Cloudflare | https://dash.cloudflare.com/ | Needs account ID + API token |
| HuggingFace | https://huggingface.co/settings/tokens | Open models |
| OpenRouter | https://openrouter.ai/keys | 50 req/day on free models |

### Step 3: Add API keys as GitHub repo secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

Add the keys you got (any subset works — at minimum, add Groq + Gemini):
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `SAMBANOVA_API_KEY`
- `CF_API_TOKEN` and `CF_ACCOUNT_ID`
- `HF_TOKEN`

Also add:
- `GH_PAT` — a GitHub Personal Access Token with `repo` scope (for the agent to commit changes back). Create one at https://github.com/settings/tokens.

### Step 4: Enable GitHub Pages

1. In your repo: **Settings → Pages → Build and deployment → Source = GitHub Actions**
2. The included `.github/workflows/deploy-pages.yml` handles deployment.
3. Your site will be live at `https://YOUR-USERNAME.github.io/REPO-NAME/`.

### Step 5: Update sitemap and robots.txt

Open `docs/sitemap.xml` and `docs/robots.txt` and replace `YOUR-USERNAME` with your actual GitHub username (and `REPO-NAME` if different).

### Step 6: Trigger the first run

Go to **Actions tab → Zero-Cost Business Autonomous Loop → Run workflow**.

The agent will now run every 30 minutes automatically.

## File Structure

```
zero-cost-ai-business/
├── .github/workflows/
│   ├── loop.yml                  # Agent loop (every 30 min)
│   └── deploy-pages.yml          # Deploy docs/ to GitHub Pages
├── agent.py                      # Main agent (agentic loop entry point)
├── llm_client.py                 # Multi-provider LLM client w/ fallback
├── budget.py                     # Daily LLM budget tracker
├── tools.py                      # Tool registry (8 tools)
├── requirements.txt
├── README.md
├── LICENSE                       # MIT
├── .gitignore
│
├── prompts/
│   └── business_prompt.md        # System prompt (minimal, non-prescriptive)
│
├── memory/                       # Agent's persistent memory
│   ├── state.md                  # Rolling summary of recent runs
│   ├── action_log.md             # Full audit log (auto-trimmed)
│   ├── blocked.md                # Blockers requiring human action
│   ├── revenue.md                # Realized profit + wallet addresses
│   ├── pending_requests.md       # Requests for human operator
│   ├── consult_request.md        # Agent's strategic Q for human
│   ├── consult_response.md       # Human's answer
│   ├── experiments.md            # A/B test & experiment results
│   ├── analytics.md              # Traffic & conversion metrics
│   └── budget.md                 # Daily LLM usage tracker (auto-managed)
│
├── docs/                         # GitHub Pages website
│   ├── index.html                # Landing page (lists all 8 tools)
│   ├── _config.yml               # Jekyll config
│   ├── sitemap.xml
│   ├── robots.txt
│   ├── assets/
│   │   ├── css/style.css
│   │   └── js/main.js
│   ├── tools/                    # 8 pre-loaded tools
│   │   ├── index.html
│   │   ├── json-formatter.html
│   │   ├── qr-generator.html
│   │   ├── base64.html
│   │   ├── password-generator.html
│   │   ├── hash-generator.html
│   │   ├── url-encoder.html
│   │   ├── uuid-generator.html
│   │   └── timestamp-converter.html
│   ├── guides/
│   │   └── crypto-tips.html      # Tip jar with all 5 wallet addresses
│   └── blog/
│       └── index.html
│
└── config/
    └── settings.json             # Agent configuration
```

## The Agent's Operating Method

The prompt is intentionally **non-prescriptive**. The agent is NOT told what tools to build or what content to write. It follows one method:

> **Run small experiments. Kill what doesn't work. Double down on what does. Log every experiment's result in experiments.md.**

The agent has:
- **Goal**: Maximize real realized profit
- **Method**: Empirical experimentation
- **Tools**: 8 file/web/experiment tools
- **Memory**: 10 files tracking state, revenue, experiments, budget, etc.
- **Autonomy**: It decides what to try

Every experiment is logged with:
- Hypothesis (what it expects to happen)
- Setup (what it did)
- Prediction (how it'll measure success)
- Result (what actually happened)
- Decision (KILL / ITERATE / SCALE)

## Security Model

- **Path allowlist**: Writes restricted to `docs/`. Reads restricted to `docs/` + `memory/`.
- **Sandboxed HTTP**: External content from `http_get` is logged but NEVER fed back to the LLM as instructions (prompt-injection defense).
- **No secrets in code**: All API keys come from environment variables / GitHub secrets.
- **No private keys**: Only public receive addresses stored. Never requested, never transmitted.
- **Kill switch**: Create a `PAUSE` file in repo root to halt the agent.
- **Action audit**: Every action logged in `action_log.md` with timestamp, model, result.

## How to Audit

Every run is fully logged:
- `memory/state.md` — Rolling summary of last 2-3 runs
- `memory/action_log.md` — Full uncapped audit log (auto-trimmed to 100 runs)
- `memory/blocked.md` — Anything blocking progress
- `memory/revenue.md` — Confirmed realized profit
- `memory/experiments.md` — All experiments and their results
- `memory/analytics.md` — Traffic and conversion metrics
- `memory/budget.md` — Daily LLM usage per provider

Check these files in the repo (or via `git log`) any time.

## How to Stop the Agent

Create a file named `PAUSE` in the repo root:
```bash
touch PAUSE
git add PAUSE && git commit -m "Pause agent" && git push
```
The agent will skip runs while `PAUSE` exists. Delete it to resume.

## Troubleshooting

**"All LLM providers failed"** — Check that at least one API key is set as a repo secret. The agent logs detailed failure reasons in `memory/blocked.md`.

**"Skipped — daily budget exhausted"** — All providers hit their daily limit. The agent will resume at UTC midnight when budgets reset. This is by design — it spreads usage across the day.

**"Workflow doesn't run"** — GitHub Actions scheduled workflows:
- Only run on the default branch
- Can be delayed 5-15 minutes during high load
- Are skipped if the repo has been inactive for 60 days (GitHub auto-disables scheduled workflows)

**"GitHub Pages not deploying"** — Make sure Settings → Pages → Source is set to "GitHub Actions".

**"Agent keeps choosing 'done' immediately"** — Check `memory/budget.md` to see if budget is low. Also check the agent's reasoning in `memory/action_log.md` — it may need a nudge via `prompts/business_prompt.md`.

## Customization

- **Change run frequency**: Edit `.github/workflows/loop.yml` → `cron:` line. Current: `*/30 * * * *` (every 30 min).
- **Change daily limits**: Edit `budget.py` → `DAILY_LIMITS` dict.
- **Change max steps per run**: Edit `budget.py` → `get_max_steps_for_budget()` or the budget level thresholds in `get_budget_level()`.
- **Add a new LLM provider**: Add a `_call_<provider>()` function in `llm_client.py` and register it in `PROVIDERS`.
- **Add a new tool**: Add a `tool_<name>()` function in `tools.py` and register it in `TOOLS`.
- **Change the agent's strategy**: Edit `prompts/business_prompt.md` — this is the agent's "brain".

## License

MIT — see [LICENSE](LICENSE).

## Support This Project

If this template helps you make money, consider tipping the original wallets listed in `docs/guides/crypto-tips.html`. Or fork it and build your own.
