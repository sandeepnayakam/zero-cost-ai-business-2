# Revenue Tracking

**Purpose:** Log all REALIZED profit (money actually received, not projections).
**Rule:** Only realized profit counts. Never include unconfirmed or unrealized revenue.

## Total Realized Profit
$0.06 (carried over from prior experiment)

## Transaction Log
| Date       | Source                | Amount  | Currency | Notes                              |
|------------|----------------------|---------|----------|------------------------------------|
| 2026-07-31 | Previous experiment  | $0.06   | USD      | Prior run, realized profit         |

## Crypto Wallets (Public Receive Addresses Only — Never Request Private Keys)

| Chain                | Address                                              |
|----------------------|------------------------------------------------------|
| Bitcoin (BTC)        | `bc1qh3areygq598ntxht0yp5yv87ej7g6aqvw8fl4z`        |
| Ethereum / ERC-20    | `0xd6DFE6b54bF3dBC919Fde57009452fe6bbb0D997`        |
| Ronin                | `0xAa4E76e5Be5334c0f2Fe0716C42B2FC61D4c150B`        |
| Solana (SOL)         | `2emXSLoziaB5wdC8y48ovbu41agh9PzR5ro8o7kRDUvM`      |
| Tron / USDT-TRC20    | `TJxkyJW57Tb8qmvvv5rCh3L2FYssRvWFEv`                |

## How to Verify Incoming Tips (for the agent)
- **Ethereum**: `https://api.etherscan.io/api?module=account&action=balance&address=0xd6DFE6b54bF3dBC919Fde57009452fe6bbb0D997&tag=latest&apikey=YourApiKey` (free, no key needed for low volume)
- **Bitcoin**: `https://blockchain.info/q/addressbalance/bc1qh3areygq598ntxht0yp5yv87ej7g6aqvw8fl4z` (returns balance in satoshis)
- **Solana**: `https://api.mainnet-beta.solana.com` JSON-RPC `getBalance` method
- **Tron**: `https://api.trongrid.io/v1/accounts/TJxkyJW57Tb8qmvvv5rCh3L2FYssRvWFEv`

## Stripe / Gumroad / Affiliate Accounts
- Not yet configured (require human verification steps)
- When an opportunity justifies it, the agent will log a pending_request for human setup.

## Notes
- The agent must call the free APIs above to VERIFY any tip before logging it as revenue.
- "Pending" or "unconfirmed" transactions do NOT count.
- Network fees are NOT subtracted from the tip amount (we receive net of fees).
