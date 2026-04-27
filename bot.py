"""
Multi-Chain Token Launcher Bot - Complete Telegram Interface
Fixed for Render webhooks. No polling. No module-level execution.
"""
import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import TELEGRAM_TOKEN, TOKEN_NAME, TOKEN_SYMBOL, TOKEN_DECIMALS, TOKEN_SUPPLY
from wallet_manager import wallet, generate_volume_wallets
from solana_client import SolanaTrader, SolanaTokenManager, SolanaAnalytics
from volume_bot import VolumeEngine, LiquidityManager
from profit_calc import calculate_rug_profit, format_profit_report, calculate_custom_scenario
from max_extract import calculate_all_strategies, format_extraction_report, calculate_5_dollar_strategy
from lp_trap import explain_lp_trap, calculate_lp_vs_no_lp, format_lp_trap_report

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

trader = SolanaTrader()
token_mgr = SolanaTokenManager()
analytics = SolanaAnalytics()
liq_mgr = LiquidityManager()
volume_engines = {}


def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH", callback_data="m_launch"), InlineKeyboardButton("💰 WALLET", callback_data="m_wallet")],
        [InlineKeyboardButton("📊 ANALYTICS", callback_data="m_analytics"), InlineKeyboardButton("🔴 SELL", callback_data="m_sell")],
        [InlineKeyboardButton("🟢 BUY", callback_data="m_buy"), InlineKeyboardButton("💧 LIQUIDITY", callback_data="m_liquidity")],
        [InlineKeyboardButton("📈 VOLUME", callback_data="m_volume"), InlineKeyboardButton("🧮 PROFIT", callback_data="m_profit")],
        [InlineKeyboardButton("💎 MAX EXTRACTION", callback_data="m_max")],
        [InlineKeyboardButton("🪤 $5 LP TRAP", callback_data="m_lp_trap")],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="m_settings")],
    ])

def launch_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ CREATE TOKEN", callback_data="l_create")],
        [InlineKeyboardButton("🪙 MINT SUPPLY", callback_data="l_mint")],
        [InlineKeyboardButton("🌊 CREATE POOL", callback_data="l_pool")],
        [InlineKeyboardButton("🎯 AUTO LAUNCH", callback_data="l_auto")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def sell_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 25%", callback_data="s_25"), InlineKeyboardButton("🔥 50%", callback_data="s_50"), InlineKeyboardButton("🔥 100%", callback_data="s_100")],
        [InlineKeyboardButton("📉 CHUNKS (DCA)", callback_data="s_chunks")],
        [InlineKeyboardButton("💵 CUSTOM AMOUNT", callback_data="s_custom")],
        [InlineKeyboardButton("📊 CHECK BALANCE", callback_data="s_balance")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def buy_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 0.1 SOL", callback_data="b_0.1"), InlineKeyboardButton("💰 0.5 SOL", callback_data="b_0.5")],
        [InlineKeyboardButton("💰 1 SOL", callback_data="b_1.0"), InlineKeyboardButton("💰 2 SOL", callback_data="b_2.0")],
        [InlineKeyboardButton("💵 CUSTOM", callback_data="b_custom")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def volume_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ START", callback_data="v_start")],
        [InlineKeyboardButton("⏹️ STOP", callback_data="v_stop")],
        [InlineKeyboardButton("📊 STATS", callback_data="v_stats")],
        [InlineKeyboardButton("💰 FUND", callback_data="v_fund")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def analytics_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 HOLDERS", callback_data="a_holders")],
        [InlineKeyboardButton("🏆 TOP HOLDERS", callback_data="a_top")],
        [InlineKeyboardButton("💰 PRICE", callback_data="a_price")],
        [InlineKeyboardButton("📊 FULL", callback_data="a_full")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])

def liquidity_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 FIND POOLS", callback_data="liq_find")],
        [InlineKeyboardButton("🔗 SMITHII", callback_data="liq_smithii")],
        [InlineKeyboardButton("📈 ANALYTICS", callback_data="liq_analytics")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
    ])


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
    context.user_data["mint"] = context.args[0]
    await update.message.reply_text(f"✅ Token set: `{context.args[0]}`", parse_mode="Markdown")


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data
    user_id = update.effective_user.id
    mint = context.user_data.get("mint")

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
            f"Seed: {'✅' if wallet.seed_phrase else '❌'}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 REFRESH", callback_data="m_wallet")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "m_launch":
        text = f"🚀 *Launch Center*\n\nToken: *{TOKEN_NAME}* ({TOKEN_SYMBOL})\nSupply: `{TOKEN_SUPPLY:,}`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_create":
        await query.edit_message_text("⏳ Creating token mint...", reply_markup=None)
        try:
            mint_addr, tx = token_mgr.create_mint()
            context.user_data["mint"] = mint_addr
            text = f"✅ *Mint Created!*\n\n`{mint_addr}`\n\nTx: `{tx[:20]}...`"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🪙 MINT SUPPLY", callback_data="l_mint")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")]
            ])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_mint":
        if not mint:
            await query.edit_message_text("❌ Set token first!", reply_markup=launch_kb())
            return
        await query.edit_message_text(f"⏳ Minting {TOKEN_SUPPLY:,} {TOKEN_SYMBOL}...", reply_markup=None)
        try:
            amount = TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS)
            tx = token_mgr.mint_to_wallet(mint, amount)
            text = f"✅ *Minted!*\n\n`{TOKEN_SUPPLY:,}` {TOKEN_SYMBOL}\nTx: `{tx[:20]}...`"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=launch_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "l_pool":
        if not mint:
            await query.edit_message_text("❌ Create token first!", reply_markup=launch_kb())
            return
        guide = (
            f"🌊 *Create Pool*\n\nToken: `{mint}`\n\n"
            f"🔗 [Smithii](https://tools.smithii.io/liquidity-pool/solana?base={mint})\n\n"
            f"Need ~2-5 SOL for LP"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 OPEN SMITHII", url=f"https://tools.smithii.io/liquidity-pool/solana?base={mint}")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_launch")]
        ])
        await query.edit_message_text(guide, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "l_auto":
        await query.edit_message_text("🚀 Auto launch...", reply_markup=None)
        try:
            mint_addr, tx1 = token_mgr.create_mint()
            context.user_data["mint"] = mint_addr
            await asyncio.sleep(2)
            amount = TOKEN_SUPPLY * (10 ** TOKEN_DECIMALS)
            tx2 = token_mgr.mint_to_wallet(mint_addr, amount)
            text = (
                f"✅ *Auto Launch Done!*\n\n"
                f"Mint: `{mint_addr}`\n"
                f"Supply: `{TOKEN_SUPPLY:,}`\n\n"
                f"Next: Create pool via Liquidity menu"
            )
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=launch_kb())

    elif d == "m_sell":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb())
            return
        bal = trader.get_token_balance(mint)
        holders = analytics.get_holder_count(mint)
        price = analytics.get_token_price(mint)
        value = bal["ui"] * price
        text = (
            f"🔴 *Sell Dashboard*\n\n"
            f"Token: `{mint[:10]}...`\n"
            f"Balance: `{bal['ui']:,.2f}`\n"
            f"Price: `${price:.8f}`\n"
            f"Value: `${value:.2f}`\n"
            f"Holders: `{holders}`\n\nSelect:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "s_balance":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb())
            return
        bal = trader.get_token_balance(mint)
        price = analytics.get_token_price(mint)
        text = (
            f"💼 *Balance*\n\n"
            f"Tokens: `{bal['ui']:,.2f}`\n"
            f"Price: `${price:.8f}`\n"
            f"Value: `${bal['ui'] * price:.2f}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())

    elif d in ["s_25", "s_50", "s_100"]:
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb())
            return
        pct = int(d.split("_")[1])
        bal = trader.get_token_balance(mint)
        if bal["raw"] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb())
            return
        amount = int(bal["raw"] * pct / 100)
        await query.edit_message_text(f"⏳ Selling {pct}%...", reply_markup=None)
        try:
            sig = trader.sell_token(mint, amount)
            new_bal = trader.get_token_balance(mint)
            text = f"✅ *Sold {pct}%!*\n\nTx: `{sig}`\nRemaining: `{new_bal['ui']:,.2f}`"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "s_chunks":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=sell_kb())
            return
        bal = trader.get_token_balance(mint)
        if bal["raw"] == 0:
            await query.edit_message_text("❌ Zero balance!", reply_markup=sell_kb())
            return
        await query.edit_message_text("⏳ DCA selling 5 chunks...", reply_markup=None)
        try:
            sigs = []
            chunk = bal["raw"] // 5
            for i in range(5):
                sig = trader.sell_token(mint, chunk)
                sigs.append(sig)
                if i < 4:
                    await asyncio.sleep(4)
            text = f"✅ *DCA Complete!*\n\n" + "\n".join([f"`{s[:20]}...`" for s in sigs])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=sell_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=sell_kb())

    elif d == "m_buy":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb())
            return
        price = analytics.get_token_price(mint)
        text = (
            f"🟢 *Buy*\n\n"
            f"Token: `{mint[:10]}...`\n"
            f"Price: `${price:.8f}`\n"
            f"SOL: `{trader.get_sol_balance():.3f}`\n\nSelect:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buy_kb())

    elif d in ["b_0.1", "b_0.5", "b_1.0", "b_2.0"]:
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=buy_kb())
            return
        sol_amt = float(d.split("_")[1])
        lamports = int(sol_amt * 1e9)
        await query.edit_message_text(f"⏳ Buying with {sol_amt} SOL...", reply_markup=None)
        try:
            sig = trader.buy_token(mint, lamports)
            text = f"✅ *Bought!*\n\nTx: `{sig}`"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buy_kb())
        except Exception as e:
            await query.edit_message_text(f"❌ `{str(e)}`", parse_mode="Markdown", reply_markup=buy_kb())

    elif d == "m_volume":
        running = user_id in volume_engines and volume_engines[user_id].running
        text = (
            f"📈 *Volume Bot*\n\n"
            f"Wallets: {5}\n"
            f"Status: {'🟢 Running' if running else '🔴 Stopped'}"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())

    elif d == "v_start":
        if not mint:
            await query.edit_message_text("❌ Set token first!", reply_markup=volume_kb())
            return
        if user_id in volume_engines and volume_engines[user_id].running:
            await query.edit_message_text("Already running!", reply_markup=volume_kb())
            return
        engine = VolumeEngine(mint, wallet.solana_keypair)
        engine.fund_wallets(0.3)
        result = engine.start(duration_minutes=60, buy_ratio=0.6)
        volume_engines[user_id] = engine
        await query.edit_message_text(f"▶️ {result}", reply_markup=volume_kb())

    elif d == "v_stop":
        if user_id in volume_engines:
            stats = volume_engines[user_id].stop()
            await query.edit_message_text(f"⏹️ {stats}", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Not running", reply_markup=volume_kb())

    elif d == "v_stats":
        if user_id in volume_engines:
            stats = volume_engines[user_id].get_status()
            text = (
                f"📊 *Stats*\n\n"
                f"Running: {'Yes' if stats['running'] else 'No'}\n"
                f"Trades: `{stats['trades']}`\n"
                f"Volume: `{stats['volume_sol']:.2f}` SOL"
            )
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=volume_kb())
        else:
            await query.edit_message_text("No session", reply_markup=volume_kb())

    elif d == "v_fund":
        if user_id in volume_engines:
            volume_engines[user_id].fund_wallets(0.5)
            await query.edit_message_text("💰 Funded!", reply_markup=volume_kb())
        else:
            await query.edit_message_text("Start first", reply_markup=volume_kb())

    elif d == "m_analytics":
        if not mint:
            await query.edit_message_text("❌ `/settoken <mint>` first", parse_mode="Markdown", reply_markup=main_kb())
            return
        text = f"📊 *Analytics* for `{mint[:10]}...`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=analytics_kb())

    elif d == "a_holders":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=analytics_kb())
            return
        await query.edit_message_text("⏳ Counting...", reply_markup=None)
        count = analytics.get_holder_count(mint)
        text = f"👥 *Holders:* `{count}`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=analytics_kb())

    elif d == "a_price":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=analytics_kb())
            return
        price = analytics.get_token_price(mint)
        text = f"💰 *Price:* `${price:.8f}`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=analytics_kb())

    elif d == "m_liquidity":
        text = "💧 *Liquidity*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=liquidity_kb())

    elif d == "liq_find":
        if not mint:
            await query.edit_message_text("❌ No token!", reply_markup=liquidity_kb())
            return
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
            await query.edit_message_text("❌ No token!", reply_markup=liquidity_kb())
            return
        text = f"🔗 [Create on Smithii](https://tools.smithii.io/liquidity-pool/solana?base={mint})"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 OPEN", url=f"https://tools.smithii.io/liquidity-pool/solana?base={mint}")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_liquidity")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)

    elif d == "m_profit":
        text = (
            f"🧮 *Profit Calc*\n\n"
            f"Scenario:\n"
            f"• You buy $11\n"
            f"• 10 people buy $40 ($400)\n"
            f"• You hold 90%\n"
            f"• You sell everything\n\n"
            f"How much?"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧮 CALCULATE", callback_data="p_calc")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "p_calc":
        await query.edit_message_text("🧮 Calculating...", reply_markup=None)
        calc = calculate_custom_scenario(your_buy_usd=11, your_tokens_pct=90, buyer_count=10, buyer_total_usd=400, lp_sol=2.0)
        text = format_profit_report(calc)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALC", callback_data="p_calc")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_profit")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "m_lp_trap":
        text = explain_lp_trap()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧮 SHOW MATH", callback_data="lp_math")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "lp_math":
        await query.edit_message_text("🧮 Calculating...", reply_markup=None)
        calc = calculate_lp_vs_no_lp(budget_usd=5)
        text = format_lp_trap_report(calc)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="lp_math")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_lp_trap")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "m_max":
        text = (
            f"💎 *Maximum Extraction*\n\n"
            f"Compare ALL strategies side by side:\n"
            f"• Pump.fun only ($5 budget)\n"
            f"• Minimal LP (2 SOL)\n"
            f"• Big LP (10 SOL) - THE TRAP\n"
            f"• Partner LP (BEST - $0 cost)\n\n"
            f"See exactly why adding liquidity KILLS profit."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 $5 Budget", callback_data="max_5")],
            [InlineKeyboardButton("💰 $300 Budget", callback_data="max_300")],
            [InlineKeyboardButton("⚙️ CUSTOM", callback_data="max_custom")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_main")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "max_5":
        await query.edit_message_text("🧮 Calculating $5 budget strategies...", reply_markup=None)
        text = calculate_5_dollar_strategy()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="max_5")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_max")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "max_300":
        await query.edit_message_text("🧮 Calculating $300 budget strategies...", reply_markup=None)
        results = calculate_all_strategies(budget_usd=300)
        text = format_extraction_report(results)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RECALCULATE", callback_data="max_300")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="m_max")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "m_settings":
        addrs = wallet.get_all_addresses()
        text = (
            f"⚙️ *Settings*\n\n"
            f"Solana: `{addrs['solana'][:16]}...`\n"
            f"EVM: `{addrs['ethereum'][:16]}...`\n\n"
            f"Token: {TOKEN_NAME} ({TOKEN_SYMBOL})\n"
            f"Supply: {TOKEN_SUPPLY:,}\n\n"
            f"/settoken `<mint>`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb())


# ═══════════════════════════════════════════════════════
# WEBHOOK APPLICATION BUILDER (NO POLLING)
# ═══════════════════════════════════════════════════════

def create_bot_application():
    """Create bot application for webhook mode. Does NOT start polling."""
    if not TELEGRAM_TOKEN:
        logger.error("[BOT] No TELEGRAM_TOKEN found!")
        return None

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settoken", set_token))
    application.add_handler(CallbackQueryHandler(router))

    return application
