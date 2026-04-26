# Arbitrage Bot v6

Automated arbitrage bot running on Base network across multiple DEXes.

## Features
- Real-time price comparison across 4 DEXes
- Automatic swap execution when opportunity found
- Safe stop-loss and minimum profit threshold

## Supported DEXes
- Uniswap V3
- Aerodrome
- BaseSwap
- SushiSwap

## Setup
1. Create `.env` file:

ALCHEMY_URL=your_alchemy_url
PRIVATE_KEY=your_private_key
CUZDAN_ADRESI=your_wallet_address


2. Install dependencies:

pip3 install web3 python-dotenv requests

3. Run:

python3 arbitraj_bot_v6.py

## Configuration
| Parameter | Default | Description |
|---|---|---|
| MIN_KAR_YUZDE | 0.5 | Minimum profit % to execute trade |
| ISLEM_USDC | 4.0 | Trade amount in USD |
| TARAMA_SURESI | 8 | Scan interval in seconds |

## Warning
This bot uses real funds. Use at your own risk.
