# Project Plan: Hyperliquid Spot-Perp Arbitrage Bot

## 1. Introduction

This document outlines the development plan for an automated trading bot designed to execute spot-perpetual arbitrage strategies on the Hyperliquid exchange. The bot's primary goal is to systematically generate profit by capitalizing on two key market phenomena: **funding rates** and **basis**. It operates with a strong emphasis on risk management to ensure sustainable, long-term operation.

## 2. Core Strategy & Philosophy

The bot's strategy is guided by three core principles:

- **Unified Opportunity Analysis**: Instead of evaluating opportunities on multiple metrics, the bot calculates a single, comprehensive **Opportunity Score** for every asset. This score represents the net, immediate profitability of an arbitrage position, combining the potential income from the funding rate with the profit/loss from the initial price difference (basis), while accounting for all trading fees.
- **Dynamic Capital Allocation**: The bot is designed to be in the single best opportunity available at any given time. It continuously scans the market and will rotate its capital from a current position to a new, significantly more profitable one, rather than holding a decaying opportunity.
- **Risk-First Approach**: Profitability is secondary to capital preservation. The strategy's foundation is built on managing risk. A key feature is a **mandatory minimum holding period** for any position. This ensures the primary profit source (the funding payment) is captured before the bot considers exiting for non-emergency reasons, preventing unprofitable, fee-heavy trades.

## 3. System Architecture

The system consists of several components, with the `Signal Calculator` and the main `run.py` loop being central to the strategy's execution.

- **`Signal Calculator`**: This component is responsible for fetching market data, checking liquidity, and calculating the Opportunity Score for all potential assets. During an open position, it continues to calculate scores for the entire market, including the currently held asset.
- **`run.py` (Main Loop)**: This is the bot's brain. It implements the core two-state logic ("Searching" and "Position Open") and makes all final decisions regarding trade entry, exit, and rotation based on the scores provided by the `Signal Calculator`.
- **Execution Logic (TWAP)**: All entries and exits are executed using a 30-minute Time-Weighted Average Price (TWAP) strategy to minimize market impact.
    - **Implementation Note**: We will first investigate if the Hyperliquid SDK provides native TWAP order functionality. If it does, we will prioritize using it over developing a custom in-house solution.

## 4. Trading Logic: A Two-State System

The bot operates in one of two distinct states:

### State 1: Searching for Opportunity (No Position Open)

In this state, the bot is actively scanning the market to find a profitable entry point.

1.  **Market Scan**: Fetch the latest market data (order books, prices, funding rates) for all tradable spot-perpetual pairs on the exchange.
2.  **Liquidity Filter**: Remove any assets that do not have sufficient liquidity to support our target trade size (`trade_amount_usd`). This is a critical risk control to prevent excessive price slippage on entry and exit. An asset must have enough volume (e.g., a multiple of our trade size within a 30-minute window) to be considered.
3.  **Calculate Opportunity Score**: For each liquid asset, calculate its score.

    ```
    Score = (1) Next Funding Rate % + (2) Entry Basis % - (3) Round Trip Fees %
    ```
    *   **(1) Funding Rate**: The primary profit driver. This is a periodic payment made to traders holding short positions in the perpetual market. We aim to capture this payment.
    *   **(2) Basis**: The price difference between the perpetual contract and the underlying spot asset (`Perp Price - Spot Price`). A positive basis at entry contributes to profit, as we sell the perp at a higher price and buy the spot at a lower one.
    *   **(3) Round Trip Fees**: The total estimated cost of entering *and* exiting the position.

4.  **Identify Best Opportunity**: Find the asset with the highest calculated Opportunity Score.
5.  **Apply Entry Threshold**: To proceed, the top score must exceed a predefined `Entry_Threshold`. This ensures we only trade when the expected profit is significant enough to warrant the risk.
6.  **Execute Trade**: If the threshold is met, the bot begins executing the entry trade via the TWAP strategy:
    - **Long Spot, Short Perp**: It simultaneously buys the spot asset and sells the perpetual contract over the execution window.
    - Upon completion, the bot records the `entry_timestamp` and transitions to the "Position Open" state.

### State 2: Position Open (Managing the Trade)

Once in a position, the bot's focus shifts from finding an opportunity to actively managing the existing one.

- **Mandatory Holding Period**: For the first hour (`Minimum_Holding_Period`) after entry, the bot will *not* exit the position unless a critical stop-loss is hit. This period is designed to ensure at least one funding payment is collected, covering the initial transaction costs.
- **Continuous Market Scanning**: While holding, the bot continues to perform steps 1-3 from the "Searching" state for *all* assets, including the one it currently holds. This allows it to compare the quality of its current position against the best available alternative in real-time.

- **Evaluate Exit Conditions (Post-Holding Period)**: After the one-hour holding period has passed, the bot evaluates the following exit conditions in every cycle:

    1.  **Rotation Exit (Better Opportunity)**: Is there a significantly better trade available?
        - **Condition**: `best_available_score > current_position_score + Rotation_Threshold`
        - A "rotation" occurs if another asset becomes so profitable that it justifies paying the fees to switch. The `Rotation_Threshold` is a key parameter that includes the cost of closing the current position and opening the new one, plus an extra profit margin to prevent frequent, low-gain trades ("whipsawing").

    2.  **Decay Exit (Position Worsened)**: Has our current position lost its profitability?
        - **Condition**: `current_position_score < Position_Decay_Threshold`
        - If the live score of our position drops below a certain floor (e.g., a small negative percentage), it means the trade is no longer favorable. The bot will exit to prevent further losses or opportunity cost.

    3.  **Stop-Loss (Critical Safety Net - Overrides All)**: Has the basis moved sharply against us?
        - This is a hard safety rail that is always active, even during the holding period. It triggers an immediate exit if the price of the perpetual contract diverges too far from the spot price, indicating mounting unrealized losses and increased risk. This is the primary defense against unexpected market events.

- **Execution Logic**:
    - If a **Rotation Exit** is triggered, the bot exits the current position via TWAP and, upon completion, immediately enters the new, superior position via TWAP.
    - If a **Decay Exit** is triggered, the bot exits the position via TWAP and returns to the "Searching for Opportunity" state.
    - If the **Stop-Loss** is triggered, the bot immediately begins an emergency exit of the position.

## 5. Key Risks & Mitigations

- **Whipsaw Risk (Excessive Trading)**: The bot could theoretically jump between slightly different opportunities, racking up fees.
    - **Mitigation**: This is prevented by the combination of the `Minimum_Holding_Period` and the `Rotation_Threshold`, which creates a high bar for switching positions.
- **Liquidation Risk (Short Leg)**: A sudden spike in the perpetual's price could put the short position at risk of liquidation.
    - **Mitigation**: The bot will perform automated margin maintenance, adding collateral to the short position as needed to keep it safely away from the liquidation price. This is a top-priority background task.
- **Execution Risk (Price Slippage)**: The market could move against us during the 30-minute TWAP execution window.
    - **Mitigation**: The entry, rotation, and decay thresholds must be set conservatively to account for potential slippage. We accept a trade only if it's profitable enough to withstand minor price movements during execution.