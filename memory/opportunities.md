# Income Opportunities Tracker

**Purpose:** Track income opportunities the agent has discovered.
**Rule:** Every opportunity must have a source, description, potential, and status.
**Auto-capped to last 50 entries.**

## Status Values
- NEW — just discovered, not yet pursued
- RESEARCHING — agent is investigating feasibility
- BLOCKED — needs human action (KYC, account creation, etc.)
- IN_PROGRESS — agent is actively pursuing
- COMPLETED — finished (success or failure)
- ABANDONED — agent decided not to pursue

## Active Revenue Tracks (from business_prompt.md)
1. Bounties & Competitions — gitcoin.co, immunefi.com, devpost.com, ethglobal.com, itch.io, kaggle.com
2. Web3 Quests & Airdrops — layer3.xyz, galxe.com, zealy.io, airdrops.io
3. Agent Marketplace — morphic.app, similar platforms
4. Content Creation — mirror.xyz, medium.com, publish0x.com, hive.blog
5. Crypto Tips — passive, via the website tip jar
6. Affiliate Marketing — Amazon, crypto exchanges, SaaS tools
7. Digital Products — Gumroad (templates, PDFs, prompt packs)
8. Open Source Sponsorships — GitHub Sponsors
9. Microtasks & Surveys — prolific.com, usertesting.com

## How to Use This File
The agent uses the `log_opportunity` tool to add new entries. Each entry includes:
- SOURCE: platform or opportunity name
- DESCRIPTION: what it is and what's required
- POTENTIAL: estimated revenue range
- URL: direct link to the opportunity
- STATUS: current state (NEW/RESEARCHING/BLOCKED/IN_PROGRESS/COMPLETED/ABANDONED)

The agent should review this file at the start of each cycle and pursue the most promising opportunities.

---
