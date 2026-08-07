# Zero-Cost AI Business — v4 (Multi-Track Revenue)

An autonomous AI agent that runs every 30 minutes on GitHub Actions (free), pursues **9 different revenue tracks** in parallel, has CAPTCHA solving, wallet balance checking, and a formal human collaboration protocol. Zero cost, maximum autonomy, designed to actually make money.

## What Makes v4 Different

| Feature | v3 | v4 (this version) |
|---------|----|--------------------|
| Revenue tracks | 1 (crypto tips) | **9 tracks** (bounties, competitions, airdrops, content, affiliate, products, sponsorships, microtasks, tips) |
| Tools available | 8 | **14** (added CAPTCHA, wallet checker, opportunity/revenue logging, human protocol) |
| Memory files | 10 | **13** (added opportunities, competitions, human_actions, credentials) |
| Human collaboration | Generic pending_requests | **Formal protocol** with structured requests, action log, credentials tracker |
| CAPTCHA solving | None | **Vision-based** (Gemini) for simple text CAPTCHAs |
| Wallet verification | None | **Read-only** balance checking for 5 chains |
| Revenue tracking | Claimed $0.06 (fake) | **$0.00 honest start** — every cent verified |

## The 9 Revenue Tracks

| # | Track | Potential | Effort | Status |
|---|---|---|---|---|
| 1 | **Bounties & Competitions** | HIGH ($100-$50K) | Medium | Gitcoin, Immunefi, hackathons, Kaggle |
| 2 | **Web3 Quests & Airdrops** | MEDIUM ($10-$500) | Low | Layer3, Galxe, Zealy, learn-and-earn |
| 3 | **Agent Marketplace** | MEDIUM (passive) | Low | Morphic, similar |
| 4 | **Content Creation** | MEDIUM ($10-$1000) | Medium | Mirror.xyz, Medium, Publish0x |
| 5 | **Crypto Tips** | LOW | Passive | Existing tip jar |
| 6 | **Affiliate Marketing** | MEDIUM | Medium | Amazon, crypto exchanges |
| 7 | **Digital Products** | MEDIUM ($1-$9 each) | Medium | Gumroad |
| 8 | **Open Source Sponsorships** | LOW | Passive | GitHub Sponsors |
| 9 | **Microtasks & Surveys** | LOW | Low | Prolific, UserTesting |

## New Capabilities

### CAPTCHA Solving
- Uses Gemini's vision API to solve simple text CAPTCHAs
- For legitimate use only (account registration, directory submission)
- Every solve is logged to `memory/captcha_log.md` for audit
- Does NOT support reCAPTCHA, hCaptcha, Cloudflare Turnstile
- Ethics: only for ToS-compliant purposes, never for spam/scraping

### Wallet Balance Checking (Read-Only)
- Checks balances on Bitcoin, Ethereum, Solana, Tron, Ronin
- Uses free public APIs (no API key needed)
- **NEVER signs transactions** — purely read-only
- Every check logged to `memory/wallet_balances.md`
- Agent can verify if tips actually arrived before logging revenue

### Human Collaboration Protocol
- Structured `request_human_action` tool
- Requests include: action_type, platform, steps, why, priority
- `memory/human_actions.md` tracks completed human work
- `memory/credentials.md` tracks which platforms are available
- Agent reads these at start of each cycle to know what's unlocked

### Opportunity Tracking
- `memory/opportunities.md` — income opportunities discovered
- `memory/competitions.md` — active bounties/hackathons being pursued
- Status tracking: NEW → RESEARCHING → IN_PROGRESS → COMPLETED
- Agent reviews these each cycle to prioritize work

## File Structure

```
zero-cost-ai-business/
├── .github/workflows/
│   ├── loop.yml                  # Agent loop (every 30 min)
│   └── deploy-pages.yml          # Deploy docs/ to GitHub Pages
├── agent.py                      # Main agent (agentic loop)
├── llm_client.py                 # 7-provider LLM client w/ fallback
├── budget.py                     # Daily LLM budget tracker
├── tools.py                      # 14-tool registry (sandboxed)
├── captcha.py                    # NEW: CAPTCHA solving (vision-based)
├── wallet.py                     # NEW: Read-only wallet balance checker
├── human_protocol.py             # NEW: Human collaboration protocol
├── requirements.txt
├── README.md
├── LICENSE                       # MIT
├── .gitignore
│
├── prompts/
│   └── business_prompt.md        # System prompt (9 revenue tracks)
│
├── memory/                       # Agent's persistent memory (13 files)
│   ├── state.md                  # Rolling summary
│   ├── action_log.md             # Full audit log
│   ├── blocked.md                # Blockers requiring human
│   ├── revenue.md                # REALIZED profit ($0.00 start)
│   ├── pending_requests.md       # Requests for human
│   ├── opportunities.md          # NEW: Income opportunities
│   ├── competitions.md           # NEW: Bounties/hackathons
│   ├── human_actions.md          # NEW: Completed human work
│   ├── credentials.md            # NEW: Platform account status
│   ├── consult_request.md        # Strategic Q for human
│   ├── consult_response.md       # Human's answer
│   ├── experiments.md            # A/B test results
│   ├── analytics.md              # Traffic & conversion metrics
│   ├── budget.md                 # Daily LLM usage
│   ├── captcha_log.md            # NEW: CAPTCHA solve audit log (auto-created)
│   └── wallet_balances.md        # NEW: Wallet check audit log (auto-created)
│
├── docs/                         # GitHub Pages website
│   ├── index.html                # Landing page
│   ├── tools/                    # 8 pre-loaded tools
│   ├── guides/crypto-tips.html   # Tip jar
│   ├── blog/
│   └── assets/
│
└── config/
    └── settings.json
```

## Setup (15 minutes)

### Step 1: Push to GitHub
1. Create a public repo
2. Copy all files from the ZIP, preserving structure
3. Commit and push to `main`

### Step 2: Get LLM API Keys
Minimum: **Groq + Gemini** (both free, both essential)
- Groq: https://console.groq.com/keys (14K req/day)
- Gemini: https://aistudio.google.com/apikey (1,500 req/day, also enables CAPTCHA solving)

Optional but recommended: Cerebras, SambaNova, OpenRouter

### Step 3: Add GitHub Secrets
Settings → Secrets and variables → Actions → New repository secret:
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY` (optional)
- `CEREBRAS_API_KEY` (optional)
- `SAMBANOVA_API_KEY` (optional)
- `GH_PAT` — GitHub Personal Access Token (fine-grained, Contents: Read and write)

### Step 4: Enable GitHub Pages
Settings → Pages → Source = "GitHub Actions"

### Step 5: Update sitemap
Edit `docs/sitemap.xml` and `docs/robots.txt` — replace `YOUR-USERNAME` with your GitHub username

### Step 6: Trigger First Run
Actions tab → Zero-Cost Business Autonomous Loop → Run workflow

## How You Can Help the Agent

The agent will log requests to `memory/pending_requests.md`. You can help by:

### High-Impact (Unlocks Major Revenue)
1. **Create Coinbase account** — Unlocks Learn & Earn ($3-10 in crypto per course)
2. **Create Gumroad account** — Unlocks digital product sales
3. **Enable GitHub Sponsors** — Passive income from sponsors
4. **Create Kaggle account** — Unlocks ML competitions ($10K-$100K prizes)

### Medium-Impact
5. **Create Medium account** — Content monetization
6. **Create Devpost account** — Hackathon submissions
7. **Create Gitcoin account** — Web3 bounties
8. **Create Layer3/Galxe accounts** — Web3 quests

### How to Complete a Request
When the agent logs a request:
1. Read `memory/pending_requests.md`
2. Complete the requested action (create account, etc.)
3. Add API keys as GitHub Secrets (if applicable)
4. Update `memory/human_actions.md` with what you did
5. Update `memory/credentials.md` to reflect the new account

The agent will read these files on its next run and use the new capability.

## ⚠️ Critical Safety Notes

### NEVER Store Seed Phrases
- The agent only has PUBLIC wallet addresses
- It CANNOT and WILL NOT sign transactions
- Any transaction requiring a signature goes to `pending_requests.md`
- You sign manually in your wallet, paste back the tx hash
- This is the ONLY safe way to handle crypto

### CAPTCHA Solving Ethics
- Only for legitimate, ToS-compliant purposes
- NOT for mass account creation, spam, or scraping
- NOT for bypassing rate limits
- Many sites' ToS prohibit automated CAPTCHA solving
- When in doubt, the agent requests human help instead

### All Actions Are Logged
- Every CAPTCHA solve → `memory/captcha_log.md`
- Every wallet check → `memory/wallet_balances.md`
- Every agent action → `memory/action_log.md`
- Every human action → `memory/human_actions.md`
- Full audit trail for everything

## How to Stop the Agent
Create a `PAUSE` file in the repo root:
```bash
touch PAUSE
git add PAUSE && git commit -m "Pause agent" && git push
```

## Troubleshooting

**"All LLM providers failed"** — Check that API keys are set as secrets. At minimum, need GROQ_API_KEY and GEMINI_API_KEY.

**"Budget exhausted"** — All providers hit daily limit. Resets at UTC midnight.

**Agent not making money** — Check `memory/opportunities.md` to see what it's pursuing. Check `memory/pending_requests.md` to see if it needs your help. The agent needs YOU to create accounts on platforms that require KYC.

**CAPTCHA solving not working** — Requires GEMINI_API_KEY. Only works on simple text CAPTCHAs, not reCAPTCHA/hCaptcha.

## License
MIT — see [LICENSE](LICENSE).
