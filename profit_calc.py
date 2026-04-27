"""
Real profit calculator using AMM constant-product math.
"""


def calculate_rug_profit(
    creator_allocation_pct: float = 90.0,
    lp_sol: float = 2.0,
    lp_token_pct: float = 10.0,
    num_buyers: int = 10,
    buyer_usd: float = 40.0,
    sol_price: float = 150.0,
    total_supply: int = 1_000_000_000,
    decimals: int = 9
) -> dict:
    """
    Calculate exact profit from token dump using real AMM math (x*y=k).
    """
    creator_tokens = int(total_supply * creator_allocation_pct / 100)
    pool_tokens = int(total_supply * lp_token_pct / 100)
    pool_sol = lp_sol
    k = pool_tokens * pool_sol

    sim_pool_sol = pool_sol
    sim_pool_tokens = pool_tokens
    total_buyer_tokens = 0

    for i in range(num_buyers):
        buyer_sol = buyer_usd / sol_price
        new_sol = sim_pool_sol + buyer_sol
        new_tokens = k / new_sol
        tokens_out = sim_pool_tokens - new_tokens
        sim_pool_sol = new_sol
        sim_pool_tokens = new_tokens
        total_buyer_tokens += tokens_out

    price_before = sim_pool_sol / sim_pool_tokens
    price_before_usd = price_before * sol_price
    market_cap = total_supply * price_before_usd

    new_tokens = sim_pool_tokens + creator_tokens
    new_sol = k / new_tokens
    sol_received = sim_pool_sol - new_sol
    usd_received = sol_received * sol_price

    price_after = new_sol / new_tokens
    price_after_usd = price_after * sol_price
    price_drop = ((price_before - price_after) / price_before) * 100 if price_before > 0 else 0

    buyer_value_after = total_buyer_tokens * price_after_usd
    buyer_loss = (num_buyers * buyer_usd) - buyer_value_after

    return {
        "inputs": {
            "creator_allocation_pct": creator_allocation_pct,
            "lp_sol": lp_sol,
            "lp_token_pct": lp_token_pct,
            "num_buyers": num_buyers,
            "buyer_usd": buyer_usd,
            "sol_price": sol_price,
            "total_supply": total_supply,
        },
        "setup": {
            "creator_tokens": creator_tokens,
            "pool_tokens": pool_tokens,
            "initial_price_usd": (pool_sol / pool_tokens) * sol_price,
        },
        "before_dump": {
            "pool_sol": sim_pool_sol,
            "pool_sol_usd": sim_pool_sol * sol_price,
            "price_usd": price_before_usd,
            "market_cap": market_cap,
            "buyer_tokens": total_buyer_tokens,
        },
        "dump": {
            "sol_received": sol_received,
            "usd_received": usd_received,
            "creator_profit": usd_received - (lp_sol * sol_price),
            "creator_profit_if_free_mint": usd_received,
        },
        "aftermath": {
            "price_usd": price_after_usd,
            "price_drop_pct": price_drop,
            "buyer_value_now": buyer_value_after,
            "buyer_loss": buyer_loss,
            "buyer_roi_pct": ((buyer_value_after / (num_buyers * buyer_usd)) - 1) * 100,
        },
        "summary": {
            "total_invested_by_buyers": num_buyers * buyer_usd,
            "creator_extracted": usd_received,
            "extraction_rate": (usd_received / (num_buyers * buyer_usd)) * 100 if (num_buyers * buyer_usd) > 0 else 0,
        }
    }


def format_profit_report(calc: dict) -> str:
    i = calc["inputs"]
    s = calc["setup"]
    b = calc["before_dump"]
    d = calc["dump"]
    a = calc["aftermath"]
    summary = calc["summary"]

    return f"""💰 *PROFIT CALCULATOR RESULTS*

📊 *Your Setup:*
• Supply: {i['total_supply']:,} tokens
• You hold: {i['creator_allocation_pct']}% ({s['creator_tokens']:,})
• LP: {i['lp_sol']} SOL + {i['lp_token_pct']}% supply
• {i['num_buyers']} buyers x ${i['buyer_usd']} = ${summary['total_invested_by_buyers']}

📈 *Before Dump:*
• Price: `${b['price_usd']:.8f}`
• Market Cap: `${b['market_cap']:,.2f}`
• Pool: `{b['pool_sol']:.2f}` SOL (${b['pool_sol_usd']:.2f})

💥 *You Sell Everything:*
• Receive: `{d['sol_received']:.3f}` SOL
• Receive: `${d['usd_received']:,.2f}`
• Net Profit: `${d['creator_profit']:,.2f}`

💀 *Aftermath:*
• Price drops {a['price_drop_pct']:.1f}%
• New price: `${a['price_usd']:.10f}`
• Buyers' bags worth: `${a['buyer_value_now']:.2f}`
• Buyers lost: `${a['buyer_loss']:,.2f}`

🏆 *Summary:*
You extracted `${d['usd_received']:,.2f}` from `${summary['total_invested_by_buyers']}`
Extraction rate: `{summary['extraction_rate']:.1f}%`
"""


def calculate_custom_scenario(
    your_buy_usd: float = 11,
    your_tokens_pct: float = 90,
    buyer_count: int = 10,
    buyer_total_usd: float = 400,
    lp_sol: float = 2.0
):
    buyer_each = buyer_total_usd / buyer_count
    return calculate_rug_profit(
        creator_allocation_pct=your_tokens_pct,
        lp_sol=lp_sol,
        lp_token_pct=100 - your_tokens_pct,
        num_buyers=buyer_count,
        buyer_usd=buyer_each,
        sol_price=150
    )
