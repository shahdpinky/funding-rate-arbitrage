# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency perpetual futures funding rate arbitrage system that exploits funding rate differences across multiple decentralized exchanges (DEXs). The system monitors funding rates on Orderly and Hyperliquid, identifies arbitrage opportunities, and executes trades to profit from rate differences.

## Key Architecture

### Core Components
- **main.py**: CLI interface and orchestration logic
- **src/strategies/funding_rate_arbitrage.py**: Core arbitrage strategy with pandas-based rate analysis
- **src/{dex_name}/**: Individual DEX implementations with standardized interfaces:
  - `funding_rate.py`: Fetches funding rates for each DEX
  - `order.py`: Handles order execution and position management for perpetual futures
  - `spot.py`: Handles spot trading and balance management (Hyperliquid only)
  - `{dex_name}_utils.py`: DEX-specific setup and configuration

### DEX Integration Pattern
Each DEX follows a consistent interface:
- Funding rate fetching via `get_{dex}_funding_rates()`
- Order execution via `create_market_order(symbol, quantity, side)` for perpetuals
- Position management via `get_all_positions()` and `market_close_an_asset()`
- Real-time market data via `get_{perp/spot}_top_of_book()` and WebSocket subscriptions

### Environment Setup
Copy `.env.example` to `.env` and configure:
- `WALLET_ADDRESS` and `PRIVATE_KEY`: Main wallet credentials
- DEX-specific API keys and secrets for each exchange
- Orderly requires separate testnet/mainnet keys
- Hyperliquid only needs wallet credentials for testnet

## Development Commands

### Running the Application
```bash
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

## Trading Strategy Flow
1. Fetch funding rates from all DEXs simultaneously
2. Compile rates into pandas DataFrame for analysis
3. Identify rate differences (either vs Orderly or across all DEXs)
4. Execute arbitrage by shorting on high-rate DEX and longing on low-rate DEX
5. Monitor positions and manage risk

## Hyperliquid Spot Trading

### Spot Market Implementation
- **src/hyperliq/spot.py**: Complete spot trading interface following perpetual patterns
- **Asset ID Mapping**: Spot assets use index + 10000 (e.g., PURR/USDC with index 0 = asset ID 10000)
- **Order Execution**: Market and limit orders for spot trading pairs
- **Balance Management**: Get balances, spot transfers between addresses
- **Real-time Data**: WebSocket subscriptions for BBO and L2 order book data

### Real-time Market Data
Both perpetual and spot markets support:
- **Top of Book**: `get_{perp/spot}_top_of_book(symbol)` for snapshot data
- **WebSocket BBO**: `subscribe_{perp/spot}_top_of_book(symbol, callback)` for real-time best bid/ask
- **WebSocket L2**: `subscribe_{perp/spot}_l2_book(symbol, callback)` for full order book streaming
- **Subscription Management**: `unsubscribe(subscription_id)` to stop data streams

### WebSocket Data Format
```python
# Top of book callback receives:
{
    "symbol": "BTC",
    "timestamp": 1234567890,
    "best_bid": {"price": 50000.0, "size": 0.1, "n_orders": 5},
    "best_ask": {"price": 50001.0, "size": 0.2, "n_orders": 3}
}
```