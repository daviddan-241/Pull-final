from flask import Flask, request, jsonify
import os
import sys
import traceback
import logging
import asyncio

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global bot application (initialized on startup)
bot_app = None
bot_status = "starting"

@app.route("/")
def home():
    return "✅ Token Bot Running - Webhook Mode"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": bot_status})

@app.route("/debug")
def debug():
    return jsonify({
        "env": {
            "TELEGRAM_TOKEN": "set" if os.getenv("TELEGRAM_TOKEN") else "missing",
            "RENDER_EXTERNAL_URL": os.getenv("RENDER_EXTERNAL_URL", "not set"),
            "PORT": os.getenv("PORT", "10000"),
        },
        "bot_status": bot_status,
        "python_version": sys.version
    })

@app.route(f"/webhook/<token>", methods=["POST"])
def webhook(token):
    """Handle Telegram webhook updates."""
    from telegram import Update

    if bot_app is None:
        logger.error("[WEBHOOK] Bot app not initialized")
        return "Bot not initialized", 500

    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, bot_app.bot)

        # Process update in the event loop
        loop = asyncio.get_event_loop()
        loop.create_task(bot_app.process_update(update))

        return "ok", 200
    except Exception as e:
        logger.error(f"[WEBHOOK ERROR] {e}", exc_info=True)
        return "error", 500

def init_bot():
    """Initialize the bot application and set webhook."""
    global bot_app, bot_status

    try:
        logger.info("[BOT] Initializing...")
        from bot import create_bot_application

        bot_app = create_bot_application()
        if bot_app is None:
            bot_status = "error: no token"
            logger.error("[BOT] Failed to create application")
            return

        # Initialize the application
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bot_app.initialize())

        # Get webhook URL
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url:
            # Try to construct from request or use fallback
            render_url = os.getenv("WEBHOOK_URL", "")

        token = os.getenv("TELEGRAM_TOKEN", "")

        if render_url and token:
            webhook_path = f"/webhook/{token}"
            webhook_url = f"{render_url.rstrip('/')}{webhook_path}"

            logger.info(f"[BOT] Setting webhook: {webhook_url}")

            # Set webhook
            loop.run_until_complete(bot_app.bot.set_webhook(webhook_url))
            loop.run_until_complete(bot_app.start())

            bot_status = "running (webhook)"
            logger.info("[BOT] Webhook bot started successfully!")
        else:
            bot_status = "error: missing RENDER_EXTERNAL_URL or TELEGRAM_TOKEN"
            logger.warning(f"[BOT] Cannot start webhook - URL: {bool(render_url)}, Token: {bool(token)}")

    except Exception as e:
        bot_status = f"error: {str(e)}"
        logger.error(f"[BOT ERROR] {e}", exc_info=True)

# Initialize bot on startup
init_bot()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"[MAIN] Flask starting on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
