"""
Real Pump.fun client:
  - bonding curve state via pump.fun frontend API
  - buy / sell pre-graduation tokens via PumpPortal local API
  - GraduationPusher background worker that buys on the curve in chunks
    until the token graduates or budget is exhausted.
"""
import os
import logging
import threading
import requests

from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from wallet_manager import wallet

logger = logging.getLogger(__name__)

RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
PUMP_API = "https://frontend-api.pump.fun"
PUMPPORTAL = "https://pumpportal.fun/api/trade-local"
GRADUATION_SOL = 85.0   # ~85 SOL raised on the curve = graduation

_client = Client(RPC_URL, commitment=Confirmed)


# ─────────────────────────────────────────────────────────────
# READS
# ─────────────────────────────────────────────────────────────
def get_curve_state(mint: str) -> dict | None:
    """Fetch the live bonding-curve state. Returns None for non-pumpfun tokens."""
    try:
        r = requests.get(f"{PUMP_API}/coins/{mint}", timeout=10,
                         headers={"User-Agent": "tg-bot/1.0"})
        if r.status_code != 200:
            return None
        d = r.json()
        real_sol = float(d.get("real_sol_reserves", 0)) / 1e9
        virt_sol = float(d.get("virtual_sol_reserves", 0)) / 1e9
        virt_tok = float(d.get("virtual_token_reserves", 0))
        total = float(d.get("total_supply", 0))
        return {
            "name": d.get("name"),
            "symbol": d.get("symbol"),
            "creator": d.get("creator"),
            "complete": bool(d.get("complete", False)),
            "real_sol_reserves": real_sol,
            "virtual_sol_reserves": virt_sol,
            "virtual_token_reserves": virt_tok,
            "total_supply": total,
            "usd_market_cap": float(d.get("usd_market_cap", 0)),
            "market_id": d.get("market_id"),
            "raydium_pool": d.get("raydium_pool"),
            "king_ts": d.get("king_of_the_hill_timestamp"),
            "graduation_pct": min(100.0, real_sol / GRADUATION_SOL * 100.0),
            "sol_to_graduate": max(0.0, GRADUATION_SOL - real_sol),
        }
    except Exception as e:
        logger.warning(f"get_curve_state failed: {e}")
        return None


def get_recent_trades(mint: str, limit: int = 10) -> list[dict]:
    try:
        r = requests.get(f"{PUMP_API}/trades/{mint}?limit={limit}&offset=0",
                         timeout=10, headers={"User-Agent": "tg-bot/1.0"})
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception as e:
        logger.warning(f"get_recent_trades failed: {e}")
        return []


def is_pumpfun_pre_graduation(mint: str) -> bool:
    s = get_curve_state(mint)
    return s is not None and not s["complete"]


# ─────────────────────────────────────────────────────────────
# TRADES (PumpPortal local API → returns serialized tx → we sign + send)
# ─────────────────────────────────────────────────────────────
def _send_signed(raw_tx_bytes: bytes, payer: Keypair) -> str:
    vtx = VersionedTransaction.from_bytes(raw_tx_bytes)
    signed = VersionedTransaction(vtx.message, [payer])
    sig = _client.send_raw_transaction(bytes(signed),
                                       opts=TxOpts(skip_preflight=False)).value
    return str(sig)


class PumpFunTrader:
    """Trade pump.fun bonding-curve tokens. Free, no API key required."""

    def __init__(self, payer: Keypair | None = None):
        self.payer = payer or wallet.solana_keypair
        self.pubkey = self.payer.pubkey()

    def _trade(self, mint: str, action: str, amount: float,
               denominated_in_sol: bool, slippage_pct: int = 10,
               priority_fee: float = 0.0005) -> str:
        body = {
            "publicKey": str(self.pubkey),
            "action": action,
            "mint": mint,
            "amount": amount,
            "denominatedInSol": "true" if denominated_in_sol else "false",
            "slippage": slippage_pct,
            "priorityFee": priority_fee,
            "pool": "pump",
        }
        r = requests.post(PUMPPORTAL, json=body, timeout=25)
        if r.status_code != 200:
            raise RuntimeError(f"PumpPortal {r.status_code}: {r.text[:200]}")
        return _send_signed(r.content, self.payer)

    def buy(self, mint: str, sol_amount: float, slippage_pct: int = 10) -> str:
        return self._trade(mint, "buy", sol_amount, True, slippage_pct)

    def sell(self, mint: str, token_amount_ui: float, slippage_pct: int = 10) -> str:
        return self._trade(mint, "sell", token_amount_ui, False, slippage_pct)


# ─────────────────────────────────────────────────────────────
# GRADUATION PUSHER — background worker that buys until graduated
# ─────────────────────────────────────────────────────────────
class GraduationPusher:
    def __init__(self, mint: str, payer: Keypair,
                 max_budget_sol: float, chunk_sol: float = 1.0):
        self.mint = mint
        self.payer = payer
        self.trader = PumpFunTrader(payer)
        self.max_budget = float(max_budget_sol)
        self.chunk = float(chunk_sol)
        self.running = False
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self.spent_sol = 0.0
        self.buys = 0
        self.last_status = "idle"
        self.graduated = False

    def _loop(self):
        try:
            while not self._stop_evt.is_set():
                state = get_curve_state(self.mint)
                if not state:
                    self.last_status = "Curve unreachable; retrying"
                    self._stop_evt.wait(5); continue

                if state["complete"]:
                    self.graduated = True
                    self.last_status = (
                        f"🎉 GRADUATED. Final curve SOL: "
                        f"{state['real_sol_reserves']:.1f}"
                    )
                    break

                sol_needed = state["sol_to_graduate"]
                sol_left = self.max_budget - self.spent_sol

                if sol_left <= 0.005:
                    self.last_status = (
                        f"Budget exhausted. Spent {self.spent_sol:.3f} SOL "
                        f"({state['graduation_pct']:.1f}% to grad)"
                    )
                    break

                chunk = min(self.chunk, sol_needed + 0.1, sol_left)
                if chunk < 0.005:
                    self.last_status = "Chunk too small; stopping"
                    break

                try:
                    sig = self.trader.buy(self.mint, chunk)
                    self.spent_sol += chunk
                    self.buys += 1
                    self.last_status = (
                        f"Buy {chunk:.3f} SOL ✅ {sig[:10]}… | "
                        f"curve {state['real_sol_reserves'] + chunk:.1f}/"
                        f"{GRADUATION_SOL:.0f} SOL"
                    )
                    logger.info(f"[PUSH] {self.last_status}")
                except Exception as e:
                    self.last_status = f"Buy failed: {str(e)[:120]}"
                    logger.warning(f"[PUSH] {self.last_status}")
                    self._stop_evt.wait(6); continue

                self._stop_evt.wait(4)
        finally:
            self.running = False
            logger.info(
                f"[PUSH] ended | spent={self.spent_sol:.3f} buys={self.buys} "
                f"graduated={self.graduated}"
            )

    def start(self) -> str:
        if self.running:
            return "Already running"
        self._stop_evt.clear()
        self.running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name=f"push-{self.mint[:8]}"
        )
        self._thread.start()
        return (
            f"Started. Budget {self.max_budget:.2f} SOL, "
            f"chunk {self.chunk:.2f} SOL"
        )

    def stop(self) -> str:
        self._stop_evt.set()
        self.running = False
        return (
            f"Stopped. Spent {self.spent_sol:.3f} SOL across "
            f"{self.buys} buys. Graduated: {self.graduated}"
        )

    def status(self) -> dict:
        return {
            "running": self.running,
            "spent_sol": self.spent_sol,
            "buys": self.buys,
            "graduated": self.graduated,
            "last": self.last_status,
        }
