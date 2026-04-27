"""
Maximum Extraction Calculator
Compares all strategies side by side.
Shows why adding liquidity KILLS profit.
"""


def calculate_all_strategies(
    budget_usd=5,
    num_buyers=10,
    buyer_usd=40,
    sol_price=150,
    total_supply=1_000_000_000,
    creator_allocation=90
):
    """
    Compare 4 strategies:
    1. No LP (Pump.fun only) - $5 budget
    2. Minimal LP (2 SOL) - standard
    3. Big LP (10 SOL) - "increase liquidity"
    4. Partner LP (someone else provides) - best
    """

    results = {}

    # ─── STRATEGY 1: Pump.fun only ($5 budget) ───
    v_tokens = 1_073_000_000
    v_sol = 30.0
    k = v_tokens * v_sol

    your_sol = budget_usd / sol_price
    new_v_sol = v_sol + your_sol
    your_tokens_1 = v_tokens - (k / new_v_sol)
    v_sol = new_v_sol
    v_tokens = k / new_v_sol

    for _ in range(num_buyers):
        buyer_sol = buyer_usd / sol_price
        new_v_sol = v_sol + buyer_sol
        v_sol = new_v_sol
        v_tokens = k / new_v_sol

    new_v_tokens = v_tokens + your_tokens_1
    new_v_sol = k / new_v_tokens
    sol_received_1 = v_sol - new_v_sol

    results["pumpfun_only"] = {
        "name": "Pump.fun Only ($5)",
        "cost": budget_usd,
        "revenue": sol_received_1 * sol_price,
        "profit": (sol_received_1 * sol_price) - budget_usd,
        "roi": ((sol_received_1 * sol_price) / budget_usd - 1) * 100,
        "risk": "Low",
        "note": "You need to be first buyer"
    }

    # ─── STRATEGY 2: Minimal LP (2 SOL) ───
    lp_sol = 2.0
    lp_tokens = total_supply * 0.10
    creator_tokens = total_supply * (creator_allocation / 100)
    k2 = lp_tokens * lp_sol

    pool_sol = lp_sol
    pool_tokens = lp_tokens

    for _ in range(num_buyers):
        buyer_sol = buyer_usd / sol_price
        new_sol = pool_sol + buyer_sol
        new_tokens = k2 / new_sol
        pool_sol = new_sol
        pool_tokens = new_tokens

    new_tokens = pool_tokens + creator_tokens
    new_sol = k2 / new_tokens
    sol_received_2 = pool_sol - new_sol

    results["minimal_lp"] = {
        "name": "Minimal LP (2 SOL)",
        "cost": lp_sol * sol_price,
        "revenue": sol_received_2 * sol_price,
        "profit": (sol_received_2 * sol_price) - (lp_sol * sol_price),
        "roi": ((sol_received_2 * sol_price) / (lp_sol * sol_price) - 1) * 100,
        "risk": "Medium",
        "note": "Standard strategy"
    }

    # ─── STRATEGY 3: Big LP (10 SOL) - THE TRAP ───
    lp_sol_big = 10.0
    lp_tokens_big = total_supply * 0.30
    creator_tokens_big = total_supply * 0.70
    k3 = lp_tokens_big * lp_sol_big

    pool_sol = lp_sol_big
    pool_tokens = lp_tokens_big

    for _ in range(num_buyers):
        buyer_sol = buyer_usd / sol_price
        new_sol = pool_sol + buyer_sol
        new_tokens = k3 / new_sol
        pool_sol = new_sol
        pool_tokens = new_tokens

    new_tokens = pool_tokens + creator_tokens_big
    new_sol = k3 / new_tokens
    sol_received_3 = pool_sol - new_sol

    results["big_lp"] = {
        "name": "Big LP (10 SOL) ❌",
        "cost": lp_sol_big * sol_price,
        "revenue": sol_received_3 * sol_price,
        "profit": (sol_received_3 * sol_price) - (lp_sol_big * sol_price),
        "roi": ((sol_received_3 * sol_price) / (lp_sol_big * sol_price) - 1) * 100,
        "risk": "HIGH - You lose money",
        "note": "NEVER do this"
    }

    # ─── STRATEGY 4: Partner LP (BEST) ───
    lp_sol_p = 2.0
    lp_tokens_p = total_supply * 0.10
    your_tokens_p = total_supply * 0.80
    k4 = lp_tokens_p * lp_sol_p

    pool_sol = lp_sol_p
    pool_tokens = lp_tokens_p

    for _ in range(num_buyers):
        buyer_sol = buyer_usd / sol_price
        new_sol = pool_sol + buyer_sol
        new_tokens = k4 / new_sol
        pool_sol = new_sol
        pool_tokens = new_tokens

    new_tokens = pool_tokens + your_tokens_p
    new_sol = k4 / new_tokens
    sol_received_4 = pool_sol - new_sol

    results["partner_lp"] = {
        "name": "Partner LP (BEST) ✅",
        "cost": 0,
        "revenue": sol_received_4 * sol_price,
        "profit": sol_received_4 * sol_price,
        "roi": float("inf"),
        "risk": "Low",
        "note": "Someone else provides LP"
    }

    return results


def format_extraction_report(results: dict) -> str:
    """Format comparison for Telegram."""
    lines = [
        "🧮 *MAXIMUM EXTRACTION COMPARISON*",
        "",
        "💰 *Your Scenario:*",
        "• Budget: $5 (or $0)",
        "• 10 buyers x $40 = $400",
        "• You hold 90% of supply",
        "",
        "📊 *4 Strategies Compared:*",
        "",
    ]

    # Sort by profit
    sorted_results = sorted(results.items(), key=lambda x: x[1]["profit"], reverse=True)

    for key, r in sorted_results:
        emoji = "✅" if r["profit"] > 100 else "⚠️" if r["profit"] > 0 else "❌"
        lines.append(f"{emoji} *{r['name']}*")
        lines.append(f"   Cost: `${r['cost']:,.2f}`")
        lines.append(f"   Revenue: `${r['revenue']:,.2f}`")
        lines.append(f"   Profit: `${r['profit']:,.2f}`")
        lines.append(f"   ROI: `{r['roi']:.0f}%`")
        lines.append(f"   Risk: {r['risk']}")
        lines.append(f"   _{r['note']}_")
        lines.append("")

    lines.append("🏆 *WINNER: Partner LP Strategy*")
    lines.append("You pay $0, extract maximum, zero risk.")
    lines.append("")
    lines.append("⚠️ *NEVER add your own liquidity if you plan to dump.*")
    lines.append("Every SOL you add to LP is a SOL you can't extract.")

    return "\n".join(lines)


def calculate_5_dollar_strategy():
    """Special calculator for $5 budget."""
    results = calculate_all_strategies(budget_usd=5)
    return format_extraction_report(results)
