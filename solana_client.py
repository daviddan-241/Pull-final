"""
Real Solana operations: swaps, token creation, balances, analytics.
Uses Jupiter API v1 and Helius RPC.
Uses solders (not solana.transaction) for compatibility with solana>=0.30.
"""
import base64
import requests
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.system_program import CreateAccountParams, create_account
from spl.token.instructions import (
    initialize_mint, InitializeMintParams,
    mint_to, MintToParams,
    get_associated_token_address,
    create_idempotent_associated_token_account
)
from spl.token.constants import TOKEN_PROGRAM_ID

from config import RPC_SOLANA, JUPITER_API_KEY, TOKEN_DECIMALS, HELIUS_API_KEY
from wallet_manager import wallet

client = Client(RPC_SOLANA)
keypair = wallet.solana_keypair

JUPITER_QUOTE = "https://api.jup.ag/swap/v1/quote"
JUPITER_SWAP = "https://api.jup.ag/swap/v1/swap"
HEADERS = {"Content-Type": "application/json", "x-api-key": JUPITER_API_KEY}
SOL_MINT = "So11111111111111111111111111111111111111112"


class SolanaTrader:
    """Execute real Jupiter swaps with tx signing."""

    def __init__(self, kp=None):
        self.keypair = kp or keypair
        self.wallet = str(self.keypair.pubkey()) if self.keypair else ""
        self.client = Client(RPC_SOLANA)

    def get_sol_balance(self):
        try:
            if not self.keypair:
                return 0.0
            return self.client.get_balance(self.keypair.pubkey()).value / 1e9
        except:
            return 0.0

    def get_token_balance(self, mint: str):
        try:
            if not self.keypair:
                return {"ui": 0, "raw": 0, "decimals": 0}
            mint_pk = Pubkey.from_string(mint)
            ata = get_associated_token_address(self.keypair.pubkey(), mint_pk)
            resp = self.client.get_token_account_balance(ata)
            if resp.value:
                return {
                    "ui": resp.value.ui_amount or 0,
                    "raw": int(resp.value.amount),
                    "decimals": resp.value.decimals
                }
            return {"ui": 0, "raw": 0, "decimals": 0}
        except:
            return {"ui": 0, "raw": 0, "decimals": 0}

    def get_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int = 100):
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": "false"
        }
        resp = requests.get(JUPITER_QUOTE, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def execute_swap(self, quote: dict) -> str:
        payload = {
            "quoteResponse": quote,
            "userPublicKey": self.wallet,
            "wrapAndUnwrapSol": True,
            "prioritizationFeeLamports": "auto"
        }
        swap_resp = requests.post(JUPITER_SWAP, headers=HEADERS, json=payload, timeout=30)
        swap_resp.raise_for_status()
        swap_data = swap_resp.json()

        if "swapTransaction" not in swap_data:
            raise Exception(f"Jupiter error: {swap_data}")

        raw_tx = base64.b64decode(swap_data["swapTransaction"])
        tx = VersionedTransaction.from_bytes(raw_tx)
        signed_tx = VersionedTransaction(tx.message, [self.keypair])

        opts = TxOpts(skip_preflight=False, preflight_commitment="confirmed")
        result = self.client.send_transaction(signed_tx, opts=opts)
        return str(result.value)

    def sell_token(self, token_mint: str, amount_raw: int):
        quote = self.get_quote(token_mint, SOL_MINT, amount_raw)
        return self.execute_swap(quote)

    def buy_token(self, token_mint: str, sol_amount_lamports: int):
        quote = self.get_quote(SOL_MINT, token_mint, sol_amount_lamports)
        return self.execute_swap(quote)


class SolanaTokenManager:
    """Real SPL token creation and minting using solders only."""

    def __init__(self, kp=None):
        self.keypair = kp or keypair
        self.client = Client(RPC_SOLANA)

    def create_mint(self, decimals: int = TOKEN_DECIMALS):
        if not self.keypair:
            raise Exception("No keypair configured")

        mint_kp = Keypair()
        mint_len = 82
        rent = self.client.get_minimum_balance_for_rent_exemption(mint_len).value

        create_account_ix = create_account(
            CreateAccountParams(
                from_pubkey=self.keypair.pubkey(),
                to_pubkey=mint_kp.pubkey(),
                lamports=rent,
                space=mint_len,
                owner=TOKEN_PROGRAM_ID
            )
        )

        init_mint_ix = initialize_mint(
            InitializeMintParams(
                program_id=TOKEN_PROGRAM_ID,
                mint=mint_kp.pubkey(),
                decimals=decimals,
                mint_authority=self.keypair.pubkey(),
                freeze_authority=None
            )
        )

        from solders.transaction import Transaction as SoldersTransaction
        blockhash = self.client.get_latest_blockhash().value.blockhash
        tx = SoldersTransaction.new_signed_with_payer(
            [create_account_ix, init_mint_ix],
            self.keypair.pubkey(),
            [self.keypair, mint_kp],
            blockhash
        )

        result = self.client.send_transaction(tx)
        return str(mint_kp.pubkey()), str(result.value)

    def create_ata(self, mint: str, owner: str = None):
        mint_pk = Pubkey.from_string(mint)
        owner_pk = Pubkey.from_string(owner) if owner else self.keypair.pubkey()
        ata = get_associated_token_address(owner_pk, mint_pk)

        if self.client.get_account_info(ata).value:
            return str(ata)

        ix = create_idempotent_associated_token_account(
            payer=self.keypair.pubkey(),
            owner=owner_pk,
            mint=mint_pk
        )

        from solders.transaction import Transaction as SoldersTransaction
        blockhash = self.client.get_latest_blockhash().value.blockhash
        tx = SoldersTransaction.new_signed_with_payer(
            [ix],
            self.keypair.pubkey(),
            [self.keypair],
            blockhash
        )

        self.client.send_transaction(tx)
        return str(ata)

    def mint_to_wallet(self, mint: str, amount: int, recipient: str = None):
        mint_pk = Pubkey.from_string(mint)
        recipient_pk = Pubkey.from_string(recipient) if recipient else self.keypair.pubkey()
        ata = Pubkey.from_string(self.create_ata(mint, recipient))

        ix = mint_to(
            MintToParams(
                program_id=TOKEN_PROGRAM_ID,
                mint=mint_pk,
                dest=ata,
                authority=self.keypair.pubkey(),
                amount=amount
            )
        )

        from solders.transaction import Transaction as SoldersTransaction
        blockhash = self.client.get_latest_blockhash().value.blockhash
        tx = SoldersTransaction.new_signed_with_payer(
            [ix],
            self.keypair.pubkey(),
            [self.keypair],
            blockhash
        )

        result = self.client.send_transaction(tx)
        return str(result.value)


class SolanaAnalytics:
    """Real on-chain analytics via Helius RPC."""

    def __init__(self):
        self.client = Client(RPC_SOLANA)

    def get_holder_count(self, mint: str) -> int:
        try:
            url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getProgramAccounts",
                "params": [
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    {
                        "encoding": "jsonParsed",
                        "filters": [
                            {"dataSize": 165},
                            {"memcmp": {"offset": 0, "bytes": mint}}
                        ]
                    }
                ]
            }
            resp = requests.post(url, json=payload, timeout=60)
            data = resp.json()

            if "result" not in data:
                return 0

            count = 0
            for acc in data["result"]:
                try:
                    amt = int(acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
                    if amt > 0:
                        count += 1
                except:
                    continue
            return count
        except Exception as e:
            print(f"[Analytics] Holder count error: {e}")
            return 0

    def get_token_price(self, mint: str) -> float:
        try:
            url = f"https://api.jup.ag/price/v2?ids={mint}"
            resp = requests.get(url, headers={"x-api-key": JUPITER_API_KEY}, timeout=10)
            data = resp.json()
            if "data" in data and mint in data["data"]:
                return float(data["data"][mint].get("price", 0))
            return 0.0
        except:
            return 0.0
