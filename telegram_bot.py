import os
import re
import json
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from knowledge_base import run_data_collection
# ----------------------
# Telegram Bot Section
# ----------------------

# Define conversation states
INSTRUCTION, INPUT = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Data Collection Bot!\n"
        "Use /collect to provide instructions and input for data collection."
    )

async def collect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send your instructions:")
    return INSTRUCTION

async def instruction_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["instruction"] = update.message.text
    await update.message.reply_text("Now, please send your input (this could be a URL, a GitHub repo URL, or a topic):")
    return INPUT

async def input_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_instruction = context.user_data.get("instruction")
    user_input = update.message.text
    
    # Send a placeholder message to indicate that data collection is in progress
    collecting_message = await update.message.reply_text("Collecting data... Please wait.")
    
    # Run the data collection
    result_message = run_data_collection(user_instruction, user_input)
    
    # If result_message is empty or None, send a fallback message
    if not result_message or result_message.strip() == "":
        result_message = "No data was collected or an error occurred. Please try again."
    
    # Edit the initial message with the result
    await collecting_message.edit_text(result_message)
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Data collection cancelled.")
    return ConversationHandler.END

def main():
    # Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your actual Telegram bot token.
    application = ApplicationBuilder().token("7939620078:AAE3U1S37gmz4waSsJwZs2eHag5TtUFf3KM").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("collect", collect_start)],
        states={
            INSTRUCTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, instruction_received)],
            INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
