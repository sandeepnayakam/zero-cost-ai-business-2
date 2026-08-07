# Revenue Tracking

**Purpose:** Log all REALIZED profit (money actually received, not projections).
**Rule:** Only realized profit counts. Never include unconfirmed or unrealized revenue.

## Total Realized Profit
$0.00 

## Realized Revenue Log
| Date | Source | Amount | Currency | TX Hash | Notes |
|------|--------|--------|----------|---------|-------|
| (none yet — first real revenue goes here) | | | | | |

## Pending Revenue (awaiting confirmation)
| Date | Source | Expected | Currency | Status | Notes |
|------|--------|----------|----------|--------|-------|
| (none yet) | | | | | |

## Crypto Wallets (Public Receive Addresses Only — Never Request Private Keys)

| Chain                | Address                                              |
|----------------------|------------------------------------------------------|
| Bitcoin (BTC)        | `bc1qh3areygq598ntxht0yp5yv87ej7g6aqvw8fl4z`        |
| Ethereum / ERC-20    | `0xd6DFE6b54bF3dBC919Fde57009452fe6bbb0D997`        |
| Ronin                | `0xAa4E76e5Be5334c0f2Fe0716C42B2FC61D4c150B`        |
| Solana (SOL)         | `2emXSLoziaB5wdC8y48ovbu41agh9PzR5ro8o7kRDUvM`      |
| Tron / USDT-TRC20    | `TJxkyJW57Tb8qmvvv5rCh3L2FYssRvWFEv`                |

## How to Verify Incoming Tips (for the agent)
The agent can use the `check_wallet_balance` or `check_all_wallets` tools to verify balances.
All balance checks are READ-ONLY — the agent never signs transactions.

Free API endpoints used (no API key needed for low volume):
- Bitcoin: blockchain.info/q/addressbalance/{address}
- Ethereum: api.etherscan.io/api?module=account&action=balance&address={address}
- Solana: api.mainnet-beta.solana.com (JSON-RPC getBalance)
- Tron: api.trongrid.io/v1/accounts/{address}
- Ronin: api.roninchain.com/rpc/v2/addresses/{address}/balances

## Revenue Tracks (priority order)
1. Bounties & Competitions (Gitcoin, Immunefi, hackathons, game jams etc..)
2. Web3 Quests & Airdrops (Layer3, Galxe, Zealy, learn-and-earn etc..)
3. Agent Marketplace (Morphic, etc.)
4. Content Creation (Mirror.xyz, Medium, Publish0x)
5. Crypto Tips (passive, low probability)
6. Digital Products (Gumroad)
7. Open Source Sponsorships (GitHub Sponsors)
8. Microtasks & Surveys (Prolific, etc.)

## Notes
- The agent must VERIFY any tip via wallet balance checks before logging as revenue.
- "Pending" or "unconfirmed" transactions do NOT count.
- Network fees are NOT subtracted from the tip amount (we receive net of fees).
- Every revenue entry must include source, amount, currency, and (if applicable) tx_hash.
