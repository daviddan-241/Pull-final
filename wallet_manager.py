"""
Multi-chain wallet manager.
Derives Solana, Ethereum, BSC, Base, Arbitrum from single seed phrase.
"""
import hashlib
from mnemonic import Mnemonic
from solders.keypair import Keypair
from eth_account import Account

try:
    from bip32 import BIP32
    BIP32_AVAILABLE = True
except ImportError:
    BIP32_AVAILABLE = False

from config import SEED_PHRASE, PRIVATE_KEY_SOL, PRIVATE_KEY_ETH


class MultiChainWallet:
    """
    Master wallet deriving all chain keys from BIP39 seed phrase.
    """

    def __init__(self):
        self.seed_phrase = SEED_PHRASE
        self._sol_keypair = None
        self._eth_account = None
        self._seed_bytes = None

        if self.seed_phrase:
            self._derive_from_seed()
        else:
            self._use_individual_keys()

    def _derive_from_seed(self):
        try:
            mnemo = Mnemonic("english")
            if not mnemo.check(self.seed_phrase):
                print("[Wallet] Invalid seed phrase, using fallback")
                return

            self._seed_bytes = mnemo.to_seed(self.seed_phrase, passphrase="")

            # Solana
            if BIP32_AVAILABLE:
                bip32 = BIP32.from_seed(self._seed_bytes)
                sol_pk = bip32.get_privkey_from_path("m/44'/501'/0'/0'")
                self._sol_keypair = Keypair.from_seed(sol_pk[:32])
            else:
                sol_seed = hashlib.sha256(self._seed_bytes + b"solana").digest()
                self._sol_keypair = Keypair.from_seed(sol_seed[:32])

            # EVM
            if BIP32_AVAILABLE:
                bip32 = BIP32.from_seed(self._seed_bytes)
                eth_pk = bip32.get_privkey_from_path("m/44'/60'/0'/0/0")
                self._eth_account = Account.from_key(eth_pk)
            else:
                eth_seed = hashlib.sha256(self._seed_bytes + b"ethereum").digest()
                self._eth_account = Account.from_key(eth_seed)
        except Exception as e:
            print(f"[Wallet] Derivation error: {e}")

    def _use_individual_keys(self):
        if PRIVATE_KEY_SOL:
            try:
                self._sol_keypair = Keypair.from_base58_string(PRIVATE_KEY_SOL)
            except Exception as e:
                print(f"[Wallet] SOL key error: {e}")
        if PRIVATE_KEY_ETH:
            try:
                self._eth_account = Account.from_key(PRIVATE_KEY_ETH)
            except Exception as e:
                print(f"[Wallet] ETH key error: {e}")

    @property
    def solana_keypair(self):
        return self._sol_keypair

    @property
    def solana_pubkey(self):
        return str(self._sol_keypair.pubkey()) if self._sol_keypair else "Not configured"

    @property
    def eth_account(self):
        return self._eth_account

    @property
    def eth_address(self):
        return self._eth_account.address if self._eth_account else "Not configured"

    def get_all_addresses(self):
        return {
            "solana": self.solana_pubkey,
            "ethereum": self.eth_address,
            "bsc": self.eth_address,
            "base": self.eth_address,
            "arbitrum": self.eth_address,
        }


wallet = MultiChainWallet()


def generate_volume_wallets(count: int = 5):
    """Generate volume wallets using solders to_bytes/from_bytes API."""
    wallets = []
    for i in range(count):
        kp = Keypair()
        wallets.append({
            "pubkey": str(kp.pubkey()),
            "private_key": kp.to_bytes().hex(),
            "index": i
        })
    return wallets
