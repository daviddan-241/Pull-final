"""
Multi-Chain Token Launcher Bot - ALL-IN-ONE
Flask keep-alive (Render + UptimeRobot) + Telegram bot polling.
One file, one process. No dummy fallbacks. Real wallets, real RPC,
real Jupiter swaps, real Pump.fun curve reads + trades + graduation pusher.

Required env vars: TELEGRAM_TOKEN, SEED_PHRASE
Optional:          SOLANA_RPC_URL, HELIUS_RPC_URL,
                   TOKEN_NAME, TOKEN_SYMBOL, TOKEN_DECIMALS, TOKEN_SUPPLY, PORT
Start command:     python app.py
"""
import os
import asyncio
import logging
import threading
import time

from flask import Flask
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
)

# ─────────────────────────────────────────────────────────────
# ENV + LOGGING
# ─────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TOKEN_NAME    = os.getenv("TOKEN_NAME", "MyToken")
TOKEN_SYMBOL  = os.getenv("TOKEN_SYMBOL", "MTK")
TOKEN_DECIMALS = int(os.getenv("TOKEN_DECIMALS", "9"))
TOKEN_SUPPLY   = int(os.getenv("TOKEN_SUPPLY", "1000000000"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# REAL MODULE IMPORTS - no dummy fallback. Fail loudly if broken.
# ─────────────────────────────────────────────────────────────
from wallet_manager import wallet, generate_volume_wallets
from solana_client  import SolanaTrader, SolanaTokenManager, SolanaAnalytics
from volume_bot     import VolumeEngine, LiquidityManager
from profit_calc    import calculate_rug_profit, format_profit_report, calculate_custom_scenario
from max_extract    import calculate_all_strategies, format_extraction_report, calculate_5_dollar_strategy
from lp_trap        import explain_lp_trap, calculate_lp_vs_no_lp, format_lp_trap_report
from pumpfun_client import (
    get_curve_state, get_recent_trades, GraduationPusher,
    PumpFunTrader, GRADUATION_SOL,
)

trader     = SolanaTrader()
token_mgr  = SolanaTokenManager()
analytics  = SolanaAnalytics()
liq_mgr    = LiquidityManager()
volume_engines: dict[int, VolumeEngine] = {}
graduation_pushers: dict[int, GraduationPusher] = {}


# ─────────────────────────────────────────────────────────────
# BALANCE PRE-CHECK
# ─────────────────────────────────────────────────────────────
MIN_SOL = {
    "create_mint": 0.010, "mint": 0.005, "auto_launch": 0.020,
    "buy": 0.005, "sell": 0.005, "volume": 0.500, "push": 1.0,
}


async def _ensure_funded(query, action_key: str, kb, extra_sol: float = 0.0) -> bool:
    needed = MIN_SOL.get(action_key, 0.005) + float(extra_sol)
    try:
        bal = float(trader.get_sol_balance() or 0.0)
    except Exception:
        bal = 0.0
    if bal >= needed:
        return True
    text = (
        f"⚠️ *Wallet Not Funded*\n\n"
        f"This action needs at least `{needed:.4f}` SOL.\n"
        f"Current: `{bal:.4f}` SOL\n"
        f"Short by: `{max(needed - bal, 0):.4f}` SOL\n\n"
        f"💼 *Send SOL to:*\n`{wallet.solana_pubkey}`\n\nThen tap again."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return False


# ─────────────────────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────────────────────
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH",   callback_data="m_launch"),
         InlineKeyboardButton("💰 WALLET",   callback_data="m_wallet")],
        [InlineKeyboardButton("📊 ANALYTICS",callback_data="m_analytics"),
         InlineKeyboardButton("🔴 SELL",     callback_data="m_sell")],
        [InlineKeyboardButton("🟢 BUY",      callback_data="m_buy"),
         InlineKeyboardButton("💧 LIQUIDITY",callback_data="m_liquidity")],
        [InlineKeyboardButton("📈 VOLUME",   callback_data="m_volume"),
         InlineKeyboardButton("🧮 PROFIT",   callback_data="m_profit")],
        [InlineKeyboardButton("💎 MAX EXTRACTION", callback_data="m_max")],
        [InlineKeyboardButton("🪤 $5 LP TRAP",     callback_data="m_lp_trap")],
        [InlineKeyboardButton("⚙️ SETTINGS",       callback_data="m_settings")],
    ])

def launch_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ CREATE TOKEN",    callback_data="l_create")],
        [InlineKeyboardButton("🪙 MINT SUPPLY",     callback_data="l_mint")],
        [InlineKeyboardButton("🌊 CREATE POOL",     callback_data="l_pool")],
        [InlineKeyboardButton("🎯 AUTO LAUNCH",     callback_data="l_auto")],
        [InlineKeyboardButton("🐸 PUMP.FUN LAUNCH", callback_data="l_pumpfun")],
        [InlineKeyboardButton("⬅️ BACK",            callback_data="m_main")],
    ])

def sell_kb(is_pumpfun: bool = False):
    rows = [
        [InlineKeyboardButton("🔥 25%",  callback_data="s_25"),
         InlineKeyboardButton("🔥 50%",  callback_data="s_50"),
         InlineKeyboardButton("🔥 100%", callback_data="s_100")],
        [InlineKeyboardButton("📉 CHUNKS (DCA)", callback_data="s_chunks")],
        [InlineKeyboardButton("📊 CHECK BALANCE", callback_data="s_balance")],
    ]
    if is_pumpfun:
        rows.append([InlineKeyboardButton("🐸 PUMP.FUN INFO", callback_data="pf_info")])
    rows.append([InlineKeyboardButton("⬅️ BACK", callback_data="m_main")])
    return InlineKeyboardMarkup(rows)

def buy_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 0.1 SOL", callback_data="b_0.1"),
         InlineKeyboardButton("💰 0.5 SOL", callback_data="b_0.5")],
        [InlineKeyboardButton("💰 1 SOL",   callback_data="b_1.0"),
         InlineKeyboardButton("💰 2 SOL",   callback_data="b_2.0")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def volume_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ START", callback_data="v_start")],
        [InlineKeyboardButton("⏹️ STOP",  callback_data="v_stop")],
        [InlineKeyboardButton("📊 STATS", callback_data="v_stats")],
        [InlineKeyboardButton("💰 FUND",  callback_data="v_fund")],
        [InlineKeyboardButton("⬅️ BACK",  callback_data="m_main")],
    ])

def analytics_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 HOLDERS", callback_data="a_holders")],
        [InlineKeyboardButton("💰 PRICE",   callback_data="a_price")],
        [InlineKeyboardButton("⬅️ BACK",    callback_data="m_main")],
    ])

def liquidity_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 FIND POOLS", callback_data="liq_find")],
        [InlineKeyboardButton("🔗 SMITHII",    callback_data="liq_smithii")],
        [InlineKeyboardButton("⬅️ BACK",       callback_data="m_main")],
    ])

def pf_info_kb(running: bool):
    rows = [
        [InlineKeyboardButton("📋 RECENT TRADES", callback_data="pf_trades")],
        [InlineKeyboardButton("👤 DEV ACTIVITY",  callback_data="pf_dev")],
    ]
    if running:
        rows.append([InlineKeyboardButton("📡 PUSH STATUS", callback_data="pf_status")])
        rows.append([InlineKeyboardButton("⏹️ STOP PUSH",   callback_data="pf_stop")])
    else:
        rows.append([InlineKeyboardButton("🚀 PUSH TO GRADUATION", callback_data="pf_push_menu")])
    rows.append([InlineKeyboardButton("🔄 REFRESH",   callback_data="pf_info")])
    rows.append([InlineKeyboardButton("⬅️ BACK SELL", callback_data="m_sell")])
    return InlineKeyboardMarkup(rows)

def pf_push_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 1 SOL",   callback_data="pf_push_1"),
         InlineKeyboardButton("💰 5 SOL",   callback_data="pf_push_5")],
        [InlineKeyboardButton("💰 10 SOL",  callback_data="pf_push_10"),
         InlineKeyboardButton("💰 25 SOL",  callback_data="pf_push_25")],
        [InlineKeyboardButton("💰 50 SOL",  callback_data="pf_push_50"),
         InlineKeyboardButton("💰 85 SOL (full)", callback_data="pf_push_85")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="pf_info")],
    ])


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _format_curve_state(s: dict) -> str:
    if s["complete"]:
        return (
            f"🎓 *GRADUATED*\n\n"
            f"Name: *{s['name'] or '?'}* ({s['symbol'] or '?'})\n"
            f"Curve SOL raised: `{s['real_sol_reserves']:.2f}`\n"
            f"USD MC: `${s['usd_market_cap']:,.0f}`\n"
            f"Raydium pool: `{(s['raydium_pool'] or 'N/A')[:16]}...`\n"
            f"Creator: `{(s['creator'] or 'N/A')[:16]}...`"
        )
    bar_full = int(s["graduation_pct"] / 5)
    bar = "█" * bar_full + "░" * (20 - bar_full)
    return (
        f"🐸 *Pump.fun Curve*\n\n"
        f"Name: *{s['name'] or '?'}* ({s['symbol'] or '?'})\n"
        f"Status: 🟡 BONDING CURVE\n\n"
        f"`{bar}` `{s['graduation_pct']:.1f}%`\n"
        f"SOL raised: `{s['real_sol_reserves']:.2f}` / `{GRADUATION_SOL:.0f}`\n"
        f"SOL to graduate: `{s['sol_to_graduate']:.2f}`\n"
        f"USD MC: `${s['usd_market_cap']:,.0f}`\n"
        f"Creator: `{(s['creator'] or 'N/A')[:16]}...`"
    )


def _format_trades(trades: list[dict], limit: int = 8) -> str:
    if not trades:
        return "_No trades yet_"
    out = ["📋 *Recent Trades*\n"]
    for t in trades[:limit]:
        side = "🟢 BUY " if t.get("is_buy") else "🔴 SELL"
        sol = float(t.get("sol_amount", 0)) / 1e9
        user = (t.get("user") or "?")[:8]
        out.append(f"{side} `{sol:.3f}` SOL · `{user}...`")
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sol = trader.get_sol_balance()
    mint = context.user_data.get("mint", "Not set")
    text = (
        f"🤖 *{TOKEN_NAME} Multi-Chain Bot*\n\n"
        f"💼 Solana: `{wallet.solana_pubkey[:8]}...`\n"
        f"💼 ETH: `{wallet.eth_address[:10]}...`\n"
        f"💰 SOL: `{sol:.3f}` | 🪙 `{mint[:8]}...`\n\n"
        f"Choose action:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())


async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/settoken <mint>`", parse_mode="Markdown")
        return
    mint = context.args[0]
    context.user_data["mint"] = mint
    state = get_curve_state(mint)
    extra = ""
    if state:
        if state["complete"]:
            extra = "\n\n🎓 Pump.fun token (graduated to Raydium)"
        else:
            extra = (f"\n\n🐸 Pump.fun bonding curve · "
                     f"{state['graduation_pct']:.1f}% to graduation")
    await update.message.reply_text(
        f"✅ Token set: `{mint}`{extra}", parse_mode="Markdown"
    )


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data
    user_id = update.effective_user.id
    mint = context.user_data.get("mint")

    # ── MAIN / WALLET / LAUNCH ──
    if d == "m_main":
        await start(update, context)

    elif d == "m_wallet":
        sol = trader.get_sol_balance()
        addrs = wallet.get_all_addresses()
        text = (
            f"💼 *Wallets*\n\n"
            f"*Solana:* `{addrs['solana']}`\n"
            f"Balance: `{sol:.4f}` SOL\n\n"
            f"*EVM:* `{addrs['ethereum']}`\n\n"
            f"Seed loaded: ✅"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 REFRESH", callback_data="m_wallet")],
            [InlineKeyboardButton("⬅️ BACK",    callback_data="m_main")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "m_launch":
        text = f"🚀 *Launch Center*\n\nToken: *{TOKEN_NAME}* ({TOKEN_SYMBOL})\nSupply: `{TOKEN_SUPPLY:,}`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_create":
        if not await _ensure_funded(query, "create_mint", launch_kb()): return
        await query.edit_message_text("⏳ Creating token mint...", reply_markup=None)
        try:
            mint_addr, tx = token_mgr.create_mint()
            context.user_data["mint"] = mint_addr
            text = f"✅ *Mint Created!*\n\n`{mint_addr}`\n\nTx: `{tx[:20]}...`"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🪙 MINT SUPPLY", callback_data="l_mint")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")],
            ])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_mint":
        if not mint:
            await query.edit_message_text("❌ Set token first!", reply_markup=launch_kb()); return
        if not await _ensure_funded(query, "mint", launch_kb()): return
        await query.edit_message_text(f"⏳ Minting {TOKEN_SUPPLY:,} {TOKEN_SYMBOL}...", reply_markup=None)
        try:
            tx = token_mgr.mint_to_wallet(mint, TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS))
            await query.edit_message_text(
                f"✅ *Minted!*\n\n`{TOKEN_SUPPLY:,}` {TOKEN_SYMBOL}\nTx: `{tx[:20]}...`",
                parse_mode="Markdown", reply_markup=launch_kb(),
            )
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_pool":
        if not mint:
            await query.edit_message_text("❌ Create token first!", reply_markup=launch_kb()); return
        url = f"https://tools.smithii.io/liquidity-pool/solana?base={mint}"
        guide = f"🌊 *Create Pool*\n\nToken: `{mint}`\n\nNeed ~2-5 SOL for LP"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 OPEN SMITHII", url=url)],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")],
        ])
        await query.edit_message_text(guide, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "l_auto":
        if not await _ensure_funded(query, "auto_launch", launch_kb()): return
        await query.edit_message_text("🚀 Auto launch...", reply_markup=None)
        try:
            mint_addr, _ = token_mgr.create_mint()
            context.user_data["mint"] = mint_addr
            await asyncio.sleep(2)
            token_mgr.mint_to_wallet(mint_addr, TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS))
            await query.edit_message_text(
                f"✅ *Auto Launch Done!*\n\nMint: `{mint_addr}`\n"
                f"Supply: `{TOKEN_SUPPLY:,}`\n\nNext: Create pool via Liquidity menu",
                parse_mode="Markdown", reply_markup=main_kb(),
            )
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_pumpfun":
        addrs = wallet.get_all_addresses()
        text = (
            f"🐸 *Launch on a Meme Launchpad*\n\n"
            f"⚠️ *Important:* launch using the wallet shown below — "
            f"otherwise this bot won't have anything to sell.\n\n"
            f"Easiest: import this seed into Phantom / MetaMask, then launch from there.\n\n"
            f"💼 *Solana wallet (use on Pump.fun):*\n`{addrs['solana']}`\n\n"
            f"💼 *EVM wallet (use on Four.meme):*\n`{addrs['ethereum']}`\n\n"
            f"After launch, copy the mint and run:\n`/settoken <mint>`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 Pump.fun (Solana)", url="https://pump.fun/create")],
            [InlineKeyboardButton("🟡 Four.meme (BSC / EVM)", url="https://four.meme")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    # ── SELL ──
    elif d == "m_sell":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb()); return
        bal = trader.get_token_balance(mint)
        price = analytics.get_token_price(mint)
        value = bal["ui"] * price
        state = get_curve_state(mint)
        is_pf = state is not None
        pf_line = ""
        if is_pf:
            if state["complete"]:
                pf_line = "\n🎓 Graduated to Raydium"
            else:
                pf_line = f"\n🐸 Pump.fun curve · {state['graduation_pct']:.1f}% to grad"
        text = (
            f"🔴 *Sell Dashboard*\n\n"
            f"Token: `{mint[:10]}...`{pf_line}\n"
            f"Balance: `{bal['ui']:,.2f}`\n"
            f"Price: `${price:.8f}`\n"
            f"Value: `${value:.2f}`\n\nSelect:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb(is_pumpfun=is_pf))

    elif d == "s_balance":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb()); return
        bal = trader.get_token_balance(mint)
        price = analytics.get_token_price(mint)
        text = (
            f"💼 *Balance*\n\nTokens: `{bal['ui']:,.2f}`\n"
            f"Price: `${price:.8f}`\nValue: `${bal['ui'] * price:.2f}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())

    elif d in ["s_25", "s_50", "s_100"]:
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb()); return
        if not await _ensure_funded(query, "sell", sell_kb()): return
        pct = int(d.split("_")[1])
        bal = trader.get_token_balance(mint)
        if bal["raw"] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb()); return
        amount = int(bal["raw"] * pct / 100)
        await query.edit_message_text(f"⏳ Selling {pct}%...", reply_markup=None)
        try:
            sig = trader.sell_token(mint, amount)
            new_bal = trader.get_token_balance(mint)
            await query.edit_message_text(
                f"✅ *Sold {pct}%!*\n\nTx: `{sig}`\nRemaining: `{new_bal['ui']:,.2f}`",
                parse_mode="Markdown", reply_markup=sell_kb(),
            )
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "s_chunks":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb()); return
        if not await _ensure_funded(query, "sell", sell_kb()): return
        bal = trader.get_token_balance(mint)
        if bal["raw"] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb()); return
        await query.edit_message_text("⏳ DCA selling 5 chunks...", reply_markup=None)
        try:
            sigs, chunk = [], bal["raw"] // 5
            for i in range(5):
                sigs.append(trader.sell_token(mint, chunk))
                if i < 4: await asyncio.sleep(4)
            await query.edit_message_text(
                "✅ *DCA Complete!*\n\n" + "\n".join(f"`{s[:20]}...`" for s in sigs),
                parse_mode="Markdown", reply_markup=sell_kb(),
            )
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    # ── PUMP.FUN INFO + GRADUATION PUSHER ──
    elif d == "pf_info":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb()); return
        await query.edit_message_text("⏳ Reading bonding curve...", reply_markup=None)
        state = get_curve_state(mint)
        if not state:
            await query.edit_message_text("❌ Not a Pump.fun token", reply_markup=sell_kb()); return
        pusher = graduation_pushers.get(user_id)
        running = bool(pusher and pusher.running)
        await query.edit_message_text(
            _format_curve_state(state), parse_mode="Markdown",
            reply_markup=pf_info_kb(running),
        )

    elif d == "pf_trades":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=main_kb()); return
        await query.edit_message_text("⏳ Loading trades...", reply_markup=None)
        trades = get_recent_trades(mint, limit=10)
        await query.edit_message_text(
            _format_trades(trades), parse_mode="Markdown",
            reply_markup=pf_info_kb(False),
        )

    elif d == "pf_dev":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=main_kb()); return
        state = get_curve_state(mint)
        if not state:
            await query.edit_message_text("❌ Not a Pump.fun token", reply_markup=sell_kb()); return
        creator = state["creator"] or "?"
        text = (
            f"👤 *Dev / Creator*\n\n"
            f"Wallet: `{creator}`\n\n"
            f"🔗 [View on Solscan](https://solscan.io/account/{creator})\n"
            f"🔗 [Pump.fun profile](https://pump.fun/profile/{creator})"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 SOLSCAN",  url=f"https://solscan.io/account/{creator}")],
            [InlineKeyboardButton("🔗 PUMP.FUN", url=f"https://pump.fun/profile/{creator}")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="pf_info")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "pf_push_menu":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=main_kb()); return
        state = get_curve_state(mint)
        if not state:
            await query.edit_message_text("❌ Not a Pump.fun token", reply_markup=sell_kb()); return
        if state["complete"]:
            await query.edit_message_text("🎓 Already graduated", reply_markup=pf_info_kb(False)); return
        bal = trader.get_sol_balance()
        text = (
            f"🚀 *Push to Graduation*\n\n"
            f"Curve: `{state['real_sol_reserves']:.2f}` / `{GRADUATION_SOL:.0f}` SOL\n"
            f"Needed: `{state['sol_to_graduate']:.2f}` SOL "
            f"(~`${state['sol_to_graduate'] * 200:.0f}` at $200/SOL)\n\n"
            f"Your wallet: `{bal:.3f}` SOL\n\n"
            f"⚠️ This will buy in 1 SOL chunks until either the token graduates "
            f"or your selected budget runs out. You'll keep all the tokens you buy.\n\n"
            f"Pick budget cap:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=pf_push_menu_kb())

    elif d.startswith("pf_push_") and d.split("_")[-1].isdigit():
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=main_kb()); return
        budget_sol = float(d.split("_")[-1])
        if not await _ensure_funded(query, "push", pf_push_menu_kb(), extra_sol=budget_sol): return
        existing = graduation_pushers.get(user_id)
        if existing and existing.running:
            await query.edit_message_text(
                "⚠️ Pusher already running. Stop it first.",
                reply_markup=pf_info_kb(True),
            ); return
        pusher = GraduationPusher(
            mint=mint, payer=wallet.solana_keypair,
            max_budget_sol=budget_sol, chunk_sol=1.0,
        )
        msg = pusher.start()
        graduation_pushers[user_id] = pusher
        await query.edit_message_text(
            f"🚀 *Push started*\n\n{msg}\n\nUse 📡 PUSH STATUS to track.",
            parse_mode="Markdown", reply_markup=pf_info_kb(True),
        )

    elif d == "pf_status":
        pusher = graduation_pushers.get(user_id)
        if not pusher:
            await query.edit_message_text("No push session", reply_markup=pf_info_kb(False)); return
        st = pusher.status()
        text = (
            f"📡 *Push Status*\n\n"
            f"Running: {'🟢 Yes' if st['running'] else '🔴 No'}\n"
            f"Buys: `{st['buys']}`\n"
            f"Spent: `{st['spent_sol']:.3f}` SOL\n"
            f"Graduated: {'🎉 YES' if st['graduated'] else 'Not yet'}\n\n"
            f"Last: {st['last']}"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=pf_info_kb(st["running"]))

    elif d == "pf_stop":
        pusher = graduation_pushers.get(user_id)
        if not pusher:
            await query.edit_message_text("No push session", reply_markup=pf_info_kb(False)); return
        msg = pusher.stop()
        await query.edit_message_text(
            f"⏹️ {msg}", reply_markup=pf_info_kb(False),
        )

    # ── BUY ──
    elif d == "m_buy":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb()); return
        price = analytics.get_token_price(mint)
        text = (
            f"🟢 *Buy*\n\nToken: `{mint[:10]}...`\n"
            f"Price: `${price:.8f}`\nSOL: `{trader.get_sol_balance():.3f}`\n\nSelect:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buy_kb())

    elif d in ["b_0.1", "b_0.5", "b_1.0", "b_2.0"]:
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=buy_kb()); return
        sol_amt = float(d.split("_")[1])
        if not await _ensure_funded(query, "buy", buy_kb(), extra_sol=sol_amt): return
        await query.edit_message_text(f"⏳ Buying with {sol_amt} SOL...", reply_markup=None)
        try:
            sig = trader.buy_token(mint, int(sol_amt * 1e9))
            await query.edit_message_text(f"✅ *Bought!*\n\nTx: `{sig}`", parse_mode="Markdown", reply_markup=buy_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=buy_kb())

    # ── VOLUME ──
    elif d == "m_volume":
        running = user_id in volume_engines and volume_engines[user_id].running
        text = f"📈 *Volume Bot*\n\nStatus: {'🟢 Running' if running else '🔴 Stopped'}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())

    elif d == "v_start":
        if not mint:
            await query.edit_message_text("❌ Set token first!", reply_markup=volume_kb()); return
        if user_id in volume_engines and volume_engines[user_id].running:
            await query.edit_message_text("Already running!", reply_markup=volume_kb()); return
        if not await _ensure_funded(query, "volume", volume_kb()): return
        engine = VolumeEngine(mint, wallet.solana_keypair)
        engine.fund_wallets(0.3)
        result = engine.start(duration_minutes=60, buy_ratio=0.6)
        volume_engines[user_id] = engine
        await query.edit_message_text(f"▶️ {result}", reply_markup=volume_kb())

    elif d == "v_stop":
        if user_id in volume_engines:
            await query.edit_message_text(f"⏹️ {volume_engines[user_id].stop()}", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Not running", reply_markup=volume_kb())

    elif d == "v_stats":
        if user_id in volume_engines:
            s = volume_engines[user_id].get_status()
            text = (f"📊 *Stats*\n\nRunning: {'Yes' if s['running'] else 'No'}\n"
                    f"Trades: `{s['trades']}`\nVolume: `{s['volume_sol']:.2f}` SOL")
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())
        else:
            await query.edit_message_text("No session", reply_markup=volume_kb())

    elif d == "v_fund":
        if user_id in volume_engines:
            volume_engines[user_id].fund_wallets(0.5)
            await query.edit_message_text("💰 Funded!", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Start first", reply_markup=volume_kb())

    # ── ANALYTICS ──
    elif d == "m_analytics":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb()); return
        await query.edit_message_text(f"📊 *Analytics* for `{mint[:10]}...`", parse_mode="Markdown", reply_markup=analytics_kb())

    elif d == "a_holders":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=analytics_kb()); return
        await query.edit_message_text("⏳ Counting...", reply_markup=None)
        await query.edit_message_text(f"👥 *Holders:* `{analytics.get_holder_count(mint)}`",
                                      parse_mode="Markdown", reply_markup=analytics_kb())

    elif d == "a_price":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=analytics_kb()); return
        await query.edit_message_text(f"💰 *Price:* `${analytics.get_token_price(mint):.8f}`",
                                      parse_mode="Markdown", reply_markup=analytics_kb())

    # ── LIQUIDITY ──
    elif d == "m_liquidity":
        await query.edit_message_text("💧 *Liquidity*", parse_mode="Markdown", reply_markup=liquidity_kb())

    elif d == "liq_find":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=liquidity_kb()); return
        await query.edit_message_text("⏳ Searching...", reply_markup=None)
        pools = liq_mgr.find_pools(mint)
        if not pools:
            text = "❌ No pools"
        else:
            text = f"🌊 *{len(pools)} Pool(s)*\n\n"
            for p in pools[:3]:
                text += f"`{p.get('id','N/A')[:10]}...` TVL: `${p.get('tvl',0):,.0f}`\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=liquidity_kb())

    elif d == "liq_smithii":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=liquidity_kb()); return
        url = f"https://tools.smithii.io/liquidity-pool/solana?base={mint}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 OPEN", url=url)],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_liquidity")],
        ])
        await query.edit_message_text(f"🔗 [Create on Smithii]({url})",
                                      parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    # ── PROFIT / LP TRAP / MAX EXTRACTION / SETTINGS ──
    elif d == "m_profit":
        text = (
            "🧮 *Profit Calc*\n\nScenario:\n"
            "• You buy $11\n• 10 people buy $40 ($400)\n"
            "• You hold 90%\n• You sell everything\n\nHow much?"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧮 CALCULATE", callback_data="p_calc")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "p_calc":
        await query.edit_message_text("🧮 Calculating...", reply_markup=None)
        calc = calculate_custom_scenario(your_buy_usd=11, your_tokens_pct=90,
                                         buyer_count=10, buyer_total_usd=400, lp_sol=2.0)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALC", callback_data="p_calc")],
            [InlineKeyboardButton("⬅️ BACK",   callback_data="m_profit")],
        ])
        await query.edit_message_text(format_profit_report(calc), parse_mode="Markdown", reply_markup=kb)

    elif d == "m_lp_trap":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧮 SHOW MATH", callback_data="lp_math")],
            [InlineKeyboardButton("⬅️ BACK",      callback_data="m_main")],
        ])
        await query.edit_message_text(explain_lp_trap(), parse_mode="Markdown", reply_markup=kb)

    elif d == "lp_math":
        await query.edit_message_text("🧮 Calculating...", reply_markup=None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="lp_math")],
            [InlineKeyboardButton("⬅️ BACK",        callback_data="m_lp_trap")],
        ])
        await query.edit_message_text(format_lp_trap_report(calculate_lp_vs_no_lp(budget_usd=5)),
                                      parse_mode="Markdown", reply_markup=kb)

    elif d == "m_max":
        text = (
            "💎 *Maximum Extraction*\n\nCompare ALL strategies:\n"
            "• Pump.fun only ($5 budget)\n• Minimal LP (2 SOL)\n"
            "• Big LP (10 SOL) - THE TRAP\n• Partner LP (BEST - $0 cost)"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 $5 Budget",   callback_data="max_5")],
            [InlineKeyboardButton("💰 $300 Budget", callback_data="max_300")],
            [InlineKeyboardButton("⬅️ BACK",        callback_data="m_main")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "max_5":
        await query.edit_message_text("🧮 Calculating $5 budget...", reply_markup=None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="max_5")],
            [InlineKeyboardButton("⬅️ BACK",        callback_data="m_max")],
        ])
        await query.edit_message_text(calculate_5_dollar_strategy(), parse_mode="Markdown", reply_markup=kb)

    elif d == "max_300":
        await query.edit_message_text("🧮 Calculating $300 budget...", reply_markup=None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="max_300")],
            [InlineKeyboardButton("⬅️ BACK",        callback_data="m_max")],
        ])
        await query.edit_message_text(format_extraction_report(calculate_all_strategies(budget_usd=300)),
                                      parse_mode="Markdown", reply_markup=kb)

    elif d == "m_settings":
        addrs = wallet.get_all_addresses()
        text = (
            f"⚙️ *Settings*\n\n"
            f"Solana: `{addrs['solana'][:16]}...`\n"
            f"EVM: `{addrs['ethereum'][:16]}...`\n\n"
            f"Token: {TOKEN_NAME} ({TOKEN_SYMBOL})\n"
            f"Supply: {TOKEN_SUPPLY:,}\n\n/settoken `<mint>`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())


# ─────────────────────────────────────────────────────────────
# FLASK KEEP-ALIVE
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)

_bot_thread: threading.Thread | None = None
_started = False
_lock = threading.Lock()


@app.route("/")
def home():
    alive = _bot_thread.is_alive() if _bot_thread else False
    return f"✅ Token Bot Running (Polling Mode) - bot thread alive: {alive}"


@app.route("/health")
def health():
    return {
        "status": "ok",
        "mode": "polling",
        "bot_thread_alive": _bot_thread.is_alive() if _bot_thread else False,
    }


# ─────────────────────────────────────────────────────────────
# BOT THREAD LAUNCHER
# ─────────────────────────────────────────────────────────────
def _run_bot() -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())
    try:
        if not TELEGRAM_TOKEN:
            logger.error("[BOT] TELEGRAM_TOKEN missing - bot will not start.")
            return
        logger.info("[BOT] Token loaded - starting application")
        application = (
            ApplicationBuilder()
            .token(TELEGRAM_TOKEN)
            .post_init(lambda a: a.bot.delete_webhook(drop_pending_updates=True))
            .build()
        )
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("settoken", set_token))
        application.add_handler(CallbackQueryHandler(router))
        logger.info("[BOT] Starting polling from background thread...")
        application.run_polling(
            drop_pending_updates=True, poll_interval=1.0, timeout=30, stop_signals=None,
        )
    except Exception:
        logger.exception("[BOT] Crashed in background thread")


def _start_bot_once() -> None:
    global _started, _bot_thread
    with _lock:
        if _started:
            return
        _started = True
        _bot_thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
        _bot_thread.start()
        logger.info("[BOT] Background thread launched")


_start_bot_once()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)