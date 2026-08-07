#!/usr/bin/env python3
"""
Wallet Balance Checker (READ-ONLY)
===================================

Checks balances of public crypto wallet addresses using free APIs.
NEVER signs transactions. NEVER sends funds. NEVER requires private keys.

Supported chains (all use free public APIs, no API key needed for low volume):
  - bitcoin    (BTC)         — blockchain.info API
  - ethereum   (ETH + ERC-20)— etherscan.io API (free, no key for low volume)
  - solana     (SOL)         — public RPC endpoint
  - tron       (TRX + USDT)  — trongrid API
  - ronin      (RON + RON-ETH)— ronin REST API

Usage:
    from wallet import check_balance
    success, balance, currency = check_balance("bitcoin", "bc1qh3areygq598ntxht0yp5yv87ej7g6aqvw8fl4z")
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone


WALLET_LOG_FILE = "memory/wallet_balances.md"


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "ZeroCostAIBot/4.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _log_balance(chain, address, balance, currency, success, error=""):
    """Log balance check for audit."""
    entry = (
        f"\n[{_timestamp()}] {chain}\n"
        f"  Address: {address}\n"
        f"  Balance: {balance if success else 'N/A'} {currency if success else ''}\n"
        f"  Success: {success}"
    )
    if error:
        entry += f"\n  Error: {error}"
    entry += "\n"
    try:
        with open(WALLET_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def check_bitcoin_balance(address):
    """Check Bitcoin balance via blockchain.info (returns satoshis)."""
    try:
        url = f"https://blockchain.info/q/addressbalance/{address}"
        req = urllib.request.Request(url, headers={"User-Agent": "ZeroCostAIBot/4.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            satoshis = int(resp.read().decode("utf-8").strip())
        btc = satoshis / 100_000_000
        return True, btc, "BTC"
    except Exception as e:
        return False, 0, "BTC", str(e)


def check_ethereum_balance(address):
    """Check Ethereum balance via etherscan.io free API."""
    try:
        # Use the public etherscan API (no key needed for low volume)
        url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest"
        data = _get_json(url)
        if data.get("status") == "1":
            wei = int(data["result"])
            eth = wei / 10**18
            return True, eth, "ETH"
        return False, 0, "ETH", data.get("message", "Unknown error")
    except Exception as e:
        return False, 0, "ETH", str(e)


def check_solana_balance(address):
    """Check Solana balance via public RPC."""
    try:
        url = "https://api.mainnet-beta.solana.com"
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "result" in data:
            lamports = data["result"]["value"]
            sol = lamports / 10**9
            return True, sol, "SOL"
        return False, 0, "SOL", str(data.get("error", "Unknown"))
    except Exception as e:
        return False, 0, "SOL", str(e)


def check_tron_balance(address):
    """Check Tron TRX balance via trongrid free API."""
    try:
        url = f"https://api.trongrid.io/v1/accounts/{address}"
        data = _get_json(url)
        if data.get("success") and data.get("data"):
            sun = data["data"][0].get("balance", 0)
            trx = sun / 10**6
            return True, trx, "TRX"
        return True, 0, "TRX"  # Account exists but no balance
    except Exception as e:
        return False, 0, "TRX", str(e)


def check_ronin_balance(address):
    """Check Ronin balance via public API."""
    try:
        # Ronin uses a custom API
        normalized = address.replace("ronin:", "0x") if address.startswith("ronin:") else address
        url = f"https://api.roninchain.com/rpc/v2/addresses/{normalized}/balances"
        data = _get_json(url)
        if "balances" in data:
            # Returns multiple tokens
            ron_balance = 0
            for token in data["balances"]:
                if token.get("symbol") == "RON":
                    ron_balance = float(token.get("balance", 0)) / 10**18
                    break
            return True, ron_balance, "RON"
        return False, 0, "RON", "No balance field"
    except Exception as e:
        return False, 0, "RON", str(e)


# Registry of chain checkers
CHAIN_CHECKERS = {
    "bitcoin":   check_bitcoin_balance,
    "btc":       check_bitcoin_balance,
    "ethereum":  check_ethereum_balance,
    "eth":       check_ethereum_balance,
    "solana":    check_solana_balance,
    "sol":       check_solana_balance,
    "tron":      check_tron_balance,
    "trx":       check_tron_balance,
    "ronin":     check_ronin_balance,
}


def check_balance(chain, address):
    """
    Check the balance of a wallet address.

    Args:
        chain: One of 'bitcoin', 'ethereum', 'solana', 'tron', 'ronin'
               (or their tickers: 'btc', 'eth', 'sol', 'trx')
        address: The public wallet address

    Returns:
        (success, balance, currency) or (success, 0, currency, error) on failure
    """
    chain = chain.lower().strip()
    checker = CHAIN_CHECKERS.get(chain)
    if not checker:
        return False, 0, chain.upper(), f"Unsupported chain: {chain}"

    result = checker(address)
    if len(result) == 3:
        success, balance, currency = result
        _log_balance(chain, address, balance, currency, success)
        return success, balance, currency
    else:
        success, balance, currency, error = result
        _log_balance(chain, address, balance, currency, success, error)
        return success, balance, currency, error


# Pre-configured wallets from the project
PROJECT_WALLETS = {
    "bitcoin":   "bc1qh3areygq598ntxht0yp5yv87ej7g6aqvw8fl4z",
    "ethereum":  "0xd6DFE6b54bF3dBC919Fde57009452fe6bbb0D997",
    "ronin":     "0xAa4E76e5Be5334c0f2Fe0716C42B2FC61D4c150B",
    "solana":    "2emXSLoziaB5wdC8y48ovbu41agh9PzR5ro8o7kRDUvM",
    "tron":      "TJxkyJW57Tb8qmvvv5rCh3L2FYssRvWFEv",
}


def check_all_project_wallets():
    """
    Check balances of all project wallets.
    Returns dict: {chain: (success, balance, currency)}
    """
    results = {}
    for chain, address in PROJECT_WALLETS.items():
        results[chain] = check_balance(chain, address)
    return results


if __name__ == "__main__":
    print("Checking all project wallet balances...")
    print()
    results = check_all_project_wallets()
    for chain, result in results.items():
        if len(result) == 3:
            success, balance, currency = result
            status = "✓" if success else "✗"
            print(f"  {status} {chain:10s} {balance:>15.8f} {currency}")
        else:
            success, balance, currency, error = result
            print(f"  ✗ {chain:10s} ERROR: {error}")
