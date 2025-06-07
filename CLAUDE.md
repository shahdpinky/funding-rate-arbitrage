# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency perpetual futures funding rate arbitrage system that exploits funding rate differences across multiple decentralized exchanges (DEXs). The system monitors funding rates on Orderly, Hyperliquid, and ApexPro, identifies arbitrage opportunities, and executes trades to profit from rate differences.

## Key Architecture

### Core Components
- **main.py**: CLI interface and orchestration logic
- **src/strategies/funding_rate_arbitrage.py**: Core arbitrage strategy with pandas-based rate analysis
- **src/{dex_name}/**: Individual DEX implementations with standardized interfaces:
  - `funding_rate.py`: Fetches funding rates for each DEX
  - `order.py`: Handles order execution and position management
  - `{dex_name}_utils.py`: DEX-specific setup and configuration

### DEX Integration Pattern
Each DEX follows a consistent interface:
- Funding rate fetching via `get_{dex}_funding_rates()`
- Order execution via `create_market_order(symbol, quantity, side)`
- Position management via `get_all_positions()` and `market_close_an_asset()`

### Environment Setup
Copy `.env.example` to `.env` and configure:
- `WALLET_ADDRESS` and `PRIVATE_KEY`: Main wallet credentials
- DEX-specific API keys and secrets for each exchange
- Orderly requires separate testnet/mainnet keys
- Hyperliquid only needs wallet credentials for testnet
- ApexPro requires full API key setup with Stark keys

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

## Adding New DEXs
To integrate a new DEX, implement the standard interface in `src/{new_dex}/`:
1. Create funding rate fetcher
2. Implement order execution with consistent return format
3. Add position management methods
4. Update main.py DEX_rates_list and dex_options
5. Follow the pattern established by existing DEX implementations