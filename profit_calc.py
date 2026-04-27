"""Real profit math using a constant-product (x*y=k) AMM model."""

def calculate_custom_scenario(
    your_buy_usd: float,
    your_tokens_pct: float,   # % of total supply you'll end up holding
    buyer_count: int,
    buyer_total_usd: float,
    lp_sol: float,
    sol_price_usd: float = 200.0,
    total_supply: float = 1_000_000_000.0,
) -> dict:
    """Simulate: you seed a pool with lp_sol + (your_tokens_pct% of supply),
    others buy `buyer_total_usd`, you then dump everything you hold."""
    pool_sol = lp_sol
    pool_tok = total_supply * (your_tokens_pct / 100.0)
    k = pool_sol * pool_tok

    # Your initial buy with USD before others arrive
    your_sol_in = your_buy_usd / sol_price_usd
    new_pool_sol = pool_sol + your_sol_in
    new_pool_tok = k / new_pool_sol
    your_tokens_bought = pool_tok - new_pool_tok
    pool_sol, pool_tok, k = new_pool_sol, new_pool_tok, new_pool_sol * new_pool_tok

    # Others buy
    others_sol_in = buyer_total_usd / sol_price_usd
    new_pool_sol = pool_sol + others_sol_in
    new_pool_tok = k / new_pool_sol
    pool_sol, pool_tok, k = new_pool_sol, new_pool_tok, new_pool_sol * new_pool_tok

    # You dump everything you hold (LP-side tokens already returned + your buy)
    your_total_tokens = your_tokens_bought
    new_pool_tok = pool_tok + your_total_tokens
    new_pool_sol = k / new_pool_tok
    sol_out = pool_sol - new_pool_sol

    cost_usd = your_buy_usd + (lp_sol * sol_price_usd)
    revenue_usd = sol_out * sol_price_usd + (new_pool_sol * sol_price_usd)  # LP withdraw too
    profit_usd = revenue_usd - cost_usd

    return {
        "cost_usd": cost_usd,
        "revenue_usd": revenue_usd,
        "profit_usd": profit_usd,
        "your_tokens": your_tokens_bought,
        "final_pool_sol": new_pool_sol,
        "sol_extracted": sol_out,
    }


def format_profit_report(c: dict) -> str:
    return (
        "🧮 *Profit Report*\n\n"
        f"Cost:       `${c['cost_usd']:,.2f}`\n"
        f"Revenue:    `${c['revenue_usd']:,.2f}`\n"
        f"*Profit:*   `${c['profit_usd']:,.2f}`\n\n"
        f"Tokens bought: `{c['your_tokens']:,.0f}`\n"
        f"SOL extracted: `{c['sol_extracted']:.3f}`\n"
        f"Pool SOL after: `{c['final_pool_sol']:.3f}`"
    )


def calculate_rug_profit(buy_usd: float, others_usd: float, sol_price: float = 200.0) -> dict:
    return calculate_custom_scenario(
        your_buy_usd=buy_usd, your_tokens_pct=90.0,
        buyer_count=10, buyer_total_usd=others_usd,
        lp_sol=2.0, sol_price_usd=sol_price,
    )