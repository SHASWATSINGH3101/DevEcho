import logging
import asyncio
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from knowledge_base import run_data_collection
from knowledge_retrieve import run_rag
import subprocess
import time
from tone_config import get_current_tone, set_tone, list_available_tones

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set your Telegram Bot Token - REPLACE THIS WITH YOUR ACTUAL TOKEN
TELEGRAM_BOT_TOKEN = '7939620078:AAE3U1S37gmz4waSsJwZs2eHag5TtUFf3KM'  # Replace with your actual bot token

# User states
WAITING_FOR_INSTRUCTION = 1
WAITING_FOR_INPUT = 2
PROCESSING = 3

user_states = {}
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    user_states[user_id] = WAITING_FOR_INSTRUCTION
    
    await update.message.reply_text(
        "Welcome to DevEcho - Social Media Post Generator! 🚀\n\n"
        "This bot helps you create professional social media posts based on any content.\n\n"
        "Commands:\n"
        "/new - Start a new post generation\n"
        "/tone - Change the tone of your posts\n"
        "/help - Get help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "📚 *DevEcho Social Media Post Generator Help* 📚\n\n"
        "*Commands:*\n"
        "/new - Start a new post generation\n"
        "/tone - Change the tone of your posts\n"
        "/help - Show this help message\n\n"
        
        "*How to use:*\n"
        "1. Type /new to start\n"
        "2. Enter your instructions (what you want posts about)\n"
        "3. Provide your content (URL, GitHub repo, or topic)\n"
        "4. Wait for the bot to generate posts\n"
        "5. Use /tone to change the writing style\n\n"
        
        "*Content types:*\n"
        "- GitHub repository URL (https://github.com/user/repo)\n"
        "- Any website URL\n"
        "- General topic (just type it in)\n\n"
        
        "*Available tones:*\n"
        "- professional: Clear, authoritative language\n"
        "- casual: Conversational, approachable style\n"
        "- educational: Instructive, explanatory approach\n"
        "- persuasive: Compelling, convincing language",
        parse_mode='Markdown'
    )

async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of creating a new post."""
    user_id = update.effective_user.id
    user_states[user_id] = WAITING_FOR_INSTRUCTION
    user_data[user_id] = {}
    
    await update.message.reply_text(
        "Let's create some social media posts! 📝\n\n"
        "First, tell me what you want to post about. Be as specific as possible."
    )

async def tone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change the tone of posts."""
    # Create keyboard with available tones
    keyboard = []
    available_tones = list_available_tones()
    current_tone = get_current_tone()
    
    # Create rows with 2 tones per row
    row = []
    for i, tone in enumerate(available_tones):
        marker = "✓ " if tone == current_tone else ""
        row.append(InlineKeyboardButton(f"{marker}{tone}", callback_data=f"tone_{tone}"))
        
        if (i + 1) % 2 == 0 or i == len(available_tones) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Current tone: *{current_tone}*\n\n"
        "Select the tone for your social media posts:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("tone_"):
        tone = query.data.replace("tone_", "")
        set_tone(tone)
        
        await query.edit_message_text(
            f"Tone set to: *{tone}*\n\n"
            "Your future posts will use this tone.",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Initialize user state if not exists
    if user_id not in user_states:
        user_states[user_id] = WAITING_FOR_INSTRUCTION
        user_data[user_id] = {}
    
    state = user_states[user_id]
    
    if state == WAITING_FOR_INSTRUCTION:
        user_data[user_id]['instruction'] = message_text
        user_states[user_id] = WAITING_FOR_INPUT
        
        await update.message.reply_text(
            "Great! Now provide your content.\n\n"
            "This can be:\n"
            "- A GitHub repository URL\n"
            "- A website URL\n"
            "- A general topic to research"
        )
    
    elif state == WAITING_FOR_INPUT:
        user_states[user_id] = PROCESSING
        user_data[user_id]['input'] = message_text
        
        # Send processing message
        processing_message = await update.message.reply_text(
            "⏳ Processing your request...\n"
            "This may take a minute or two."
        )
        
        # Get user instruction and input
        instruction = user_data[user_id]['instruction']
        user_input = user_data[user_id]['input']
        
        try:
            # Run the data collection and RAG process
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            # Run processes asynchronously
            result = await run_process(instruction, user_input)
            
            if result:
                await processing_message.edit_text(
                    "✅ Content processed successfully!\n"
                    "Generating social media posts..."
                )
                
                # Run post generation
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                await run_post_gen()
                
                # Send the generated posts
                twitter_posts = await load_posts("./twitter_posts/twitterpost.json")
                linkedin_posts = await load_posts("./linkedin_posts/linkedinpost.json")
                
                # Format and send Twitter posts
                if twitter_posts:
                    # Split Twitter posts if too long
                    tweet_message = "🐦 *Twitter Posts:*\n\n"
                    for post in twitter_posts:
                        tweet_content = f"*Draft {post['draft_number']}:*\n{post['content']}\n\n"
                        
                        # Add sources if they exist
                        if post.get('sources') and len(post['sources']) > 0:
                            tweet_content += "*Sources:*\n"
                            for source in post['sources']:
                                tweet_content += f"- {source}\n"
                            tweet_content += "\n"
                        
                        # Check if adding this content would make the message too long
                        if len(tweet_message + tweet_content) > 4000:
                            # Send the current batch and start a new one
                            await update.message.reply_text(tweet_message, parse_mode='Markdown')
                            tweet_message = tweet_content
                        else:
                            tweet_message += tweet_content
                    
                    # Send any remaining content
                    if tweet_message:
                        await update.message.reply_text(tweet_message, parse_mode='Markdown')
                
                # Format and send LinkedIn posts
                if linkedin_posts:
                    # Split LinkedIn posts if too long
                    linkedin_message = "💼 *LinkedIn Posts:*\n\n"
                    for post in linkedin_posts:
                        linkedin_content = f"*Draft {post['draft_number']}:*\n{post['content']}\n\n"
                        
                        # Add sources if they exist
                        if post.get('sources') and len(post['sources']) > 0:
                            linkedin_content += "*Sources:*\n"
                            for source in post['sources']:
                                linkedin_content += f"- {source}\n"
                            linkedin_content += "\n"
                        
                        # Check if adding this content would make the message too long
                        if len(linkedin_message + linkedin_content) > 4000:
                            # Send the current batch and start a new one
                            await update.message.reply_text(linkedin_message, parse_mode='Markdown')
                            linkedin_message = linkedin_content
                        else:
                            linkedin_message += linkedin_content
                    
                    # Send any remaining content
                    if linkedin_message:
                        await update.message.reply_text(linkedin_message, parse_mode='Markdown')
                
                # Send final message with tone information
                current_tone = get_current_tone()
                await update.message.reply_text(
                    f"✅ Posts generated successfully using *{current_tone}* tone!\n\n"
                    "Use /new to create more posts or /tone to change the tone.",
                    parse_mode='Markdown'
                )
            else:
                await processing_message.edit_text(
                    "❌ Error processing your content.\n"
                    "Please try again with different content.\n\n"
                    "Use /new to start over."
                )
        
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            await processing_message.edit_text(
                f"❌ An error occurred while processing your request:\n"
                f"{str(e)[:100]}...\n\n"
                "Please try again later or with different content.\n"
                "Use /new to start over."
            )
        
        # Reset state
        user_states[user_id] = WAITING_FOR_INSTRUCTION

async def run_process(instruction, user_input):
    """Run the data collection and RAG process."""
    try:
        # Make sure directories exist
        os.makedirs('./data', exist_ok=True)
        os.makedirs('./query', exist_ok=True)
        os.makedirs('./output', exist_ok=True)
        
        # Run data collection
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: run_data_collection(instruction, user_input))
        
        # Wait a moment to ensure files are written
        await asyncio.sleep(1)
        
        # Check if data was collected properly
        if not os.path.exists('./data/results.txt'):
            logger.error("Data collection failed - results.txt not found")
            return False
            
        # Run RAG
        await loop.run_in_executor(None, run_rag)
        
        # Check if RAG output was generated
        if not os.path.exists('./output/result.json'):
            logger.error("RAG process failed - result.json not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error in run_process: {str(e)}")
        raise

async def run_post_gen():
    """Run the post generation process."""
    try:
        # Make sure config directory exists
        os.makedirs('./config', exist_ok=True)
        
        # Execute as a subprocess to avoid blocking
        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.run(["python", "post_gen.py"], capture_output=True, text=True)
        )
        
        # Log any stderr output
        if process.stderr:
            logger.error(f"Post generation stderr: {process.stderr}")
            
        # Check if output was generated properly
        if not os.path.exists('./twitter_posts/twitterpost.json') or not os.path.exists('./linkedin_posts/linkedinpost.json'):
            logger.error("Post generation failed - output files not found")
            return False
            
        return process.returncode == 0
    except Exception as e:
        logger.error(f"Error in run_post_gen: {str(e)}")
        raise

async def load_posts(file_path):
    """Load posts from JSON file."""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        logger.warning(f"Post file not found: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading posts from {file_path}: {str(e)}")
        return []

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_post))
    application.add_handler(CommandHandler("tone", tone_command))
    
    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Create necessary directories
    os.makedirs('./data', exist_ok=True)
    os.makedirs('./query', exist_ok=True)
    os.makedirs('./output', exist_ok=True)
    os.makedirs('./config', exist_ok=True)
    os.makedirs('./twitter_posts', exist_ok=True)
    os.makedirs('./linkedin_posts', exist_ok=True)
    
    # Log startup
    logger.info("Bot started!")
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()