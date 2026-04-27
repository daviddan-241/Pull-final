"""
The $5 in LP Trap - Educational module
Shows why putting your last $5 into LP loses money
"""


def explain_lp_trap():
    """
    Clear explanation of why adding your $5 to LP is a trap.
    """
    return """💀 *THE $5 IN LP TRAP*

You asked: "Can I put $5 in the pool to get good profits?"

Answer: *NO. You lose 41% of your potential profit.*

Here's why:

📊 *What happens when you put $5 in LP:*

1️⃣ Your $5 gets SPLIT:
   • Half becomes tokens
   • Half becomes SOL
   • It's LOCKED in the pool

2️⃣ Buyers trade against YOUR money:
   • They give SOL → take YOUR tokens
   • Your token pile shrinks
   • Your SOL pile grows

3️⃣ When you remove LP:
   • You get LESS tokens back
   • You get MORE SOL back
   • This is "Impermanent Loss"

4️⃣ You still have 950M tokens:
   • But the pool is drained
   • You can't sell them anywhere
   • They're worthless

💰 *The Math:*

❌ Put $5 in LP:
   • Cost: $5
   • LP removal: $402
   • Profit: $397
   • BUT: 950M tokens unsold = $0
   • *Total: $397*

✅ Partner provides LP:
   • Cost: $0
   • Dump 900M tokens: $668
   • *Total: $668*

🏆 *You lose $270 (41%) by putting $5 in LP!*

⚠️ *The Rule:*
NEVER put YOUR money in LP if you plan to dump.
Let someone ELSE provide liquidity.
You extract THEIR money, not yours.

💡 *What to do with $5 instead:*
• Buy your own token first (cheapest price)
• Pay for Twitter/Discord shilling
• Buy a small amount to show "activity"
• Save it for transaction fees

But NEVER add it to LP.
"""


def calculate_lp_vs_no_lp(budget_usd=5, buyer_count=10, buyer_usd=40):
    """
    Side-by-side comparison: $5 in LP vs $5 kept.
    """
    sol_price = 150

    # --- WITH $5 IN LP ---
    lp_sol = (budget_usd / sol_price) / 2
    lp_tokens = 50_000_000
    k = lp_tokens * lp_sol

    pool_sol = lp_sol
    pool_tokens = lp_tokens

    for _ in range(buyer_count):
        buyer_sol = buyer_usd / sol_price
        new_sol = pool_sol + buyer_sol
        new_tokens = k / new_sol
        pool_sol = new_sol
        pool_tokens = new_tokens

    lp_revenue = pool_sol * sol_price
    lp_profit = lp_revenue - budget_usd

    # --- WITHOUT $5 IN LP ---
    partner_lp_sol = 2.0
    partner_lp_tokens = 100_000_000
    k2 = partner_lp_tokens * partner_lp_sol
    your_tokens = 900_000_000

    pool_sol = partner_lp_sol
    pool_tokens = partner_lp_tokens

    for _ in range(buyer_count):
        buyer_sol = buyer_usd / sol_price
        new_sol = pool_sol + buyer_sol
        new_tokens = k2 / new_sol
        pool_sol = new_sol
        pool_tokens = new_tokens

    new_tokens = pool_tokens + your_tokens
    new_sol = k2 / new_tokens
    sol_received = pool_sol - new_sol
    no_lp_revenue = sol_received * sol_price
    no_lp_profit = no_lp_revenue

    return {
        "with_lp": {
            "cost": budget_usd,
            "revenue": lp_revenue,
            "profit": lp_profit,
            "unsold_tokens": 950_000_000,
        },
        "without_lp": {
            "cost": 0,
            "revenue": no_lp_revenue,
            "profit": no_lp_profit,
            "unsold_tokens": 0,
        }
    }


def format_lp_trap_report(calc: dict) -> str:
    """Format for Telegram."""
    w = calc["with_lp"]
    wo = calc["without_lp"]

    return f"""💀 *THE $5 IN LP TRAP*

You asked: "Can I put $5 in the pool?"

📊 *Comparison:*

❌ *With $5 in LP:*
   Cost: `${w['cost']}`
   LP removal: `${w['revenue']:.2f}`
   Profit: `${w['profit']:.2f}`
   Unsold tokens: `{w['unsold_tokens']:,}`
   ⚠️ You CAN'T sell these!

✅ *Without $5 in LP:*
   Cost: `${wo['cost']}`
   Token dump: `${wo['revenue']:.2f}`
   Profit: `${wo['profit']:.2f}`
   Unsold tokens: `0`

🏆 *Difference: `${wo['profit'] - w['profit']:.2f}`*

You lose money by putting $5 in LP because:
1. Your tokens get trapped in the pool
2. Buyers eat your token side
3. You can't dump your remaining bags

💡 *Rule: NEVER add YOUR money to LP if you plan to dump.*
"""
