"""
Volume boosting engine using REAL market-making.
Rotates wallets, randomizes trade sizes, mimics organic activity.
Uses solders (not solana.transaction) for compatibility with solana>=0.30.
"""
import asyncio
import random
import time
import threading
import requests
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams

from config import RPC_SOLANA, VOLUME_WALLET_COUNT, VOLUME_MIN_SOL, VOLUME_MAX_SOL, VOLUME_INTERVAL_MIN, VOLUME_INTERVAL_MAX
from solana_client import SolanaTrader
from wallet_manager import generate_volume_wallets


class VolumeEngine:
    """
    Real volume bot creating organic-looking trading activity.
    Uses multi-wallet rotation + real Jupiter swaps.
    """

    def __init__(self, token_mint: str, master_keypair=None):
        self.token_mint = token_mint
        self.master_kp = master_keypair
        self.client = Client(RPC_SOLANA)
        self.running = False
        self.thread = None
        self.stats = {"trades": 0, "volume_sol": 0.0, "start_time": None}
        self.wallets = []

    def fund_wallets(self, amount_sol: float = 0.5):
        """Fund volume wallets from master wallet using solders."""
        if not self.master_kp:
            raise Exception("No master keypair")

        self.wallets = generate_volume_wallets(VOLUME_WALLET_COUNT)

        for w in self.wallets:
            try:
                ix = transfer(TransferParams(
                    from_pubkey=self.master_kp.pubkey(),
                    to_pubkey=Pubkey.from_string(w["pubkey"]),
                    lamports=int(amount_sol * 1e9)
                ))

                from solders.transaction import Transaction as SoldersTransaction
                blockhash = self.client.get_latest_blockhash().value.blockhash
                tx = SoldersTransaction.new_signed_with_payer(
                    [ix],
                    self.master_kp.pubkey(),
                    [self.master_kp],
                    blockhash
                )

                self.client.send_transaction(tx)
                time.sleep(1)
            except Exception as e:
                print(f"[Volume] Fund error {w['pubkey'][:8]}: {e}")

        print(f"[Volume] Funded {len(self.wallets)} wallets with {amount_sol} SOL each")

    def start(self, duration_minutes: int = 60, buy_ratio: float = 0.6):
        if self.running:
            return "Already running"

        self.running = True
        self.stats["start_time"] = time.time()

        def run_loop():
            end_time = time.time() + (duration_minutes * 60)

            while self.running and time.time() < end_time:
                try:
                    w = random.choice(self.wallets)
                    kp = Keypair.from_bytes(bytes.fromhex(w["private_key"]))
                    trader = SolanaTrader(kp)

                    sol_amount = random.uniform(VOLUME_MIN_SOL, VOLUME_MAX_SOL)
                    lamports = int(sol_amount * 1e9)
                    is_buy = random.random() < buy_ratio

                    if is_buy:
                        sig = trader.buy_token(self.token_mint, lamports)
                        print(f"[Volume] BUY {sol_amount:.3f} SOL -> {sig[:16]}...")
                    else:
                        bal = trader.get_token_balance(self.token_mint)
                        if bal["raw"] > 1000:
                            sell_amount = int(bal["raw"] * random.uniform(0.1, 0.5))
                            sig = trader.sell_token(self.token_mint, sell_amount)
                            print(f"[Volume] SELL {sell_amount} tokens -> {sig[:16]}...")
                        else:
                            continue

                    self.stats["trades"] += 1
                    self.stats["volume_sol"] += sol_amount

                    sleep_sec = random.randint(VOLUME_INTERVAL_MIN, VOLUME_INTERVAL_MAX)
                    time.sleep(sleep_sec)

                except Exception as e:
                    print(f"[Volume] Trade error: {e}")
                    time.sleep(10)

            self.running = False
            print(f"[Volume] Done. Trades: {self.stats['trades']}, Volume: {self.stats['volume_sol']:.2f} SOL")

        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        return f"Volume bot started for {duration_minutes} min"

    def stop(self):
        self.running = False
        return f"Stopped. Trades: {self.stats['trades']}"

    def get_status(self):
        if not self.stats["start_time"]:
            return {"running": False, "message": "Not started"}
        elapsed = time.time() - self.stats["start_time"]
        return {
            "running": self.running,
            "elapsed_min": elapsed / 60,
            "trades": self.stats["trades"],
            "volume_sol": self.stats["volume_sol"],
            "avg_trade_sol": self.stats["volume_sol"] / max(self.stats["trades"], 1)
        }


class LiquidityManager:
    """Manage liquidity across DEXs."""

    def __init__(self):
        self.client = Client(RPC_SOLANA)

    def find_pools(self, token_mint: str):
        try:
            url = f"https://api-v3.raydium.io/pools/info/mint?mint1={token_mint}&poolType=all&pageSize=10"
            resp = requests.get(url, timeout=30)
            data = resp.json()
            if data.get("success"):
                return data.get("data", {}).get("data", [])
            return []
        except:
            return []

    def get_pool_tvl(self, pool_id: str) -> float:
        try:
            url = f"https://api-v3.raydium.io/pools/info/ids?poolIds={pool_id}"
            resp = requests.get(url, timeout=30)
            data = resp.json()
            if data.get("success") and data.get("data"):
                return data["data"][0].get("tvl", 0)
            return 0
        except:
            return 0

    def create_pool_link(self, token_mint: str) -> str:
        return f"https://tools.smithii.io/liquidity-pool/solana?base={token_mint}"
