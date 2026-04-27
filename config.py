import os
from dotenv import load_dotenv

load_dotenv()

# Master wallet
SEED_PHRASE = os.getenv("SEED_PHRASE")
PRIVATE_KEY_SOL = os.getenv("PRIVATE_KEY_SOL")
PRIVATE_KEY_ETH = os.getenv("PRIVATE_KEY_ETH")

# API keys
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
JUPITER_API_KEY = os.getenv("JUPITER_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")

# RPC
RPC_SOLANA = os.getenv("RPC_SOLANA", "https://api.mainnet-beta.solana.com")
RPC_ETHEREUM = os.getenv("RPC_ETHEREUM", "https://eth.llamarpc.com")
RPC_BSC = os.getenv("RPC_BSC", "https://bsc-dataseed.binance.org")
RPC_BASE = os.getenv("RPC_BASE", "https://mainnet.base.org")
RPC_ARBITRUM = os.getenv("RPC_ARBITRUM", "https://arb1.arbitrum.io/rpc")

# Token config
TOKEN_NAME = os.getenv("TOKEN_NAME", "MyToken")
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "MTK")
TOKEN_DECIMALS = int(os.getenv("TOKEN_DECIMALS", "9"))
TOKEN_SUPPLY = int(os.getenv("TOKEN_SUPPLY", "1000000000"))
TOKEN_IMAGE_URL = os.getenv("TOKEN_IMAGE_URL", "")

# Volume bot
VOLUME_WALLET_COUNT = int(os.getenv("VOLUME_WALLET_COUNT", "5"))
VOLUME_MIN_SOL = float(os.getenv("VOLUME_MIN_SOL", "0.01"))
VOLUME_MAX_SOL = float(os.getenv("VOLUME_MAX_SOL", "0.1"))
VOLUME_INTERVAL_MIN = int(os.getenv("VOLUME_INTERVAL_MIN", "30"))
VOLUME_INTERVAL_MAX = int(os.getenv("VOLUME_INTERVAL_MAX", "120"))
