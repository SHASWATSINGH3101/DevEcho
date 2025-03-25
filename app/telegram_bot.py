import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

from knowledge_base import run_data_collection
from knowledge_retrieve import run_rag
from post_gen import generate_linkedin_posts  # Updated to accept parameters (see below)
from tone_config import set_tone, get_current_tone, list_available_tones
from linkedin import get_user_info, post_to_linkedin  # New LinkedIn module import

from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Use os.getenv() to avoid KeyError
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("telegram_bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Dictionary to store conversation states for users
USER_STATES = {}

# LinkedIn token storage
LINKEDIN_TOKENS = {}

# State definitions
class State:
    IDLE = 0
    WAITING_FOR_INSTRUCTIONS = 1
    WAITING_FOR_CONTENT = 2
    WAITING_FOR_TARGET_AUDIENCE = 3
    WAITING_FOR_N_DRAFTS = 4
    PROCESSING = 5
    SELECTING_POST = 6
    WAITING_FOR_LINKEDIN_TOKEN = 7

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    USER_STATES[user.id] = State.IDLE
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your AI Social Media Assistant.\n\n"
        "I can help you create engaging posts for LinkedIn based on various sources.\n\n"
        "Use /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "📱 *Social Media Assistant Bot* 📱\n\n"
        "*Commands:*\n"
        "/new - Start a new post generation\n"
        "/tone - Change the tone of your posts\n"
        "/upload_linkedin - Upload an approved post to LinkedIn\n"
        "/help - Show this help message\n\n"
        "*How to use:*\n"
        "1. Type /new to start\n"
        "2. Enter your instructions (what you want posts about)\n"
        "3. Provide your content (URL, GitHub repo, or topic)\n"
        "4. Then, you'll be asked for the target audience and number of drafts\n"
        "5. Wait for the bot to generate posts\n"
        "6. Use /upload_linkedin to post a draft to LinkedIn"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new post generation workflow."""
    user = update.effective_user
    USER_STATES[user.id] = State.WAITING_FOR_INSTRUCTIONS
    await update.message.reply_text(
        "Let's create a new post! 📝\n\n"
        "Please enter your instructions. For example:\n"
        "- Create an informative post about AI frameworks\n"
        "- Write a technical overview of this GitHub project\n"
        "- Generate content highlighting key features"
    )

async def tone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change the tone of generated posts."""
    tones = list_available_tones()
    current_tone = get_current_tone()
    
    keyboard = []
    for tone in tones:
        marker = "✅ " if tone == current_tone else ""
        keyboard.append([InlineKeyboardButton(f"{marker}{tone.capitalize()}", callback_data=f"tone_{tone}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a tone for your posts:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    # Handle tone selection
    if query.data.startswith("tone_"):
        tone = query.data.split("_")[1]
        set_tone(tone)
        await query.edit_message_text(f"Tone set to: {tone.capitalize()} ✅")
    
    # Handle post selection for LinkedIn
    elif query.data.startswith("post_"):
        post_index = int(query.data.split("_")[1])
        user_id = update.effective_user.id
        
        # Check if user has LinkedIn token
        if user_id not in LINKEDIN_TOKENS or not LINKEDIN_TOKENS[user_id]:
            await query.edit_message_text(
                "You need to set up LinkedIn first. Please send your LinkedIn access token."
            )
            USER_STATES[user_id] = State.WAITING_FOR_LINKEDIN_TOKEN
            return
            
        # Get post content from file
        try:
            with open('./linkedin_posts/linkedinpost.json', 'r', encoding='utf-8') as f:
                posts = json.load(f)
                
            if 0 <= post_index < len(posts):
                post_content = posts[post_index]["content"]
                confirm_keyboard = [
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{post_index}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                    ]
                ]
                await query.edit_message_text(
                    f"You selected this post:\n\n{post_content}\n\nConfirm posting to LinkedIn?",
                    reply_markup=InlineKeyboardMarkup(confirm_keyboard)
                )
            else:
                await query.edit_message_text("Invalid post selection.")
        except Exception as e:
            logger.error(f"Error selecting post: {str(e)}")
            await query.edit_message_text(f"Error selecting post: {str(e)}")
    
    elif query.data.startswith("confirm_"):
        post_index = int(query.data.split("_")[1])
        user_id = update.effective_user.id

        try:
            with open('./linkedin_posts/linkedinpost.json', 'r', encoding='utf-8') as f:
                posts = json.load(f)
            if not (0 <= post_index < len(posts)):
                await query.edit_message_text("Invalid post selection.")
                return

            post_content = posts[post_index]["content"]
            
            # Add "link in the comment" line to the post content
            post_content += "\n\n**This post was created by an AI agent. Check it out:** "+" https://github.com/SHASWATSINGH3101/DevEcho"

            access_token = LINKEDIN_TOKENS.get(user_id)
            if not access_token:
                await query.edit_message_text("No LinkedIn access token found. Please provide one.")
                return

            user_info = get_user_info(access_token)
            linkedin_user_id = user_info.get("id")
            if not linkedin_user_id:
                await query.edit_message_text("Failed to retrieve LinkedIn user information. Please check your token.")
                return

            result = post_to_linkedin(access_token, linkedin_user_id, post_content)
            await query.edit_message_text(f"✅ Successfully posted to LinkedIn!\nResponse: {result}")
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to post to LinkedIn. Error: {str(e)}")

    elif query.data == "cancel":
        await query.edit_message_text("LinkedIn posting cancelled.")

async def upload_linkedin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Upload an approved post to LinkedIn."""
    user_id = update.effective_user.id
    
    try:
        if not os.path.exists('./linkedin_posts/linkedinpost.json'):
            await update.message.reply_text(
                "No posts available. Please generate posts first using /new command."
            )
            return
            
        with open('./linkedin_posts/linkedinpost.json', 'r', encoding='utf-8') as f:
            posts = json.load(f)
            
        if not posts:
            await update.message.reply_text("No posts available. Please generate posts first.")
            return
            
        if user_id not in LINKEDIN_TOKENS or not LINKEDIN_TOKENS[user_id]:
            await update.message.reply_text(
                "You need to set up LinkedIn first. Please send your LinkedIn access token."
            )
            USER_STATES[user_id] = State.WAITING_FOR_LINKEDIN_TOKEN
            return
            
        keyboard = []
        for i, post in enumerate(posts):
            keyboard.append([InlineKeyboardButton(f"Post {i+1}", callback_data=f"post_{i}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select a post to upload to LinkedIn:", reply_markup=reply_markup)
        USER_STATES[user_id] = State.SELECTING_POST
        
    except Exception as e:
        logger.error(f"Error in upload_linkedin_command: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages based on current state."""
    user = update.effective_user
    text = update.message.text.strip()

    # State machine for conversation flow
    if user.id not in USER_STATES:
        USER_STATES[user.id] = State.IDLE

    state = USER_STATES[user.id]

    if state == State.WAITING_FOR_INSTRUCTIONS:
        # Store instructions and ask for content
        context.user_data["instructions"] = text
        USER_STATES[user.id] = State.WAITING_FOR_CONTENT
        await update.message.reply_text(
            "Great! Now please provide your content. This can be:\n"
            "- A URL (e.g., https://example.com/article)\n"
            "- A GitHub repository URL (e.g., https://github.com/username/repo)\n"
            "- A topic (e.g., Artificial Intelligence)"
        )
    elif state == State.WAITING_FOR_CONTENT:
        # Store the content and then ask for target audience
        context.user_data["content"] = text
        USER_STATES[user.id] = State.WAITING_FOR_TARGET_AUDIENCE
        await update.message.reply_text("Please specify the target audience for your posts.")
    elif state == State.WAITING_FOR_TARGET_AUDIENCE:
        # Store target audience and ask for number of drafts
        context.user_data["target_audience"] = text
        USER_STATES[user.id] = State.WAITING_FOR_N_DRAFTS
        await update.message.reply_text("How many drafts would you like to generate? (e.g., 3)")
    elif state == State.WAITING_FOR_N_DRAFTS:
        # Store number of drafts and proceed to processing
        try:
            n_drafts = int(text)
            context.user_data["n_drafts"] = n_drafts
        except ValueError:
            await update.message.reply_text("Please provide a valid number for drafts.")
            return
        USER_STATES[user.id] = State.PROCESSING
        await update.message.reply_text("Processing your request... This may take a minute. ⏳")
        # Run the content processing pipeline in a background task
        context.application.create_task(
            process_content(
                update, context,
                context.user_data.get("instructions", ""),
                context.user_data.get("content", "")
            )
        )
    elif state == State.WAITING_FOR_LINKEDIN_TOKEN:
        LINKEDIN_TOKENS[user.id] = text
        try:
            user_info = get_user_info(text)
            if user_info:
                await update.message.reply_text(
                    f"✅ LinkedIn access token verified. You can now use /upload_linkedin to post content."
                )
                USER_STATES[user.id] = State.IDLE
            else:
                await update.message.reply_text(
                    "❌ Invalid LinkedIn access token. Please provide a valid token."
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error verifying token: {str(e)}")
    else:
        await update.message.reply_text(
            "I'm not sure what you want to do. Try using one of these commands:\n"
            "/new - Start a new post generation\n"
            "/tone - Change the tone of your posts\n"
            "/upload_linkedin - Upload an approved post to LinkedIn\n"
            "/help - Show this help message"
        )

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE, instructions: str, content: str) -> None:
    """Process user instructions and content to generate posts."""
    try:
        message = await update.message.reply_text("Step 1/3: Collecting data... 📊")
        # Use the async version of run_data_collection
        from knowledge_base import run_data_collection_async
        await run_data_collection_async(instructions, content)
        await message.edit_text("Step 2/3: Analyzing and retrieving information... 🔍")
        # If run_rag is synchronous and potentially blocking, consider creating an async version
        # or running it in a ThreadPoolExecutor
        await asyncio.to_thread(run_rag)  # This runs the synchronous function in a separate thread
        await message.edit_text("Step 3/3: Generating posts... ✍️")
        # Same for generate_linkedin_posts if it's synchronous
        await asyncio.to_thread(
            generate_linkedin_posts,
            target_audience=context.user_data.get("target_audience", "AI/ML engineers and researchers, Data Scientists"),
            n_drafts=context.user_data.get("n_drafts", 3)
        )
        with open('./linkedin_posts/linkedinpost.json', 'r', encoding='utf-8') as f:
            posts = json.load(f)
        await message.edit_text("✅ Posts generated successfully!")
        for i, post in enumerate(posts):
            clean_content = post['content']
            # Remove unwanted AI jargon if present
            unwanted_prefix = 'Here is a rewritten LinkedIn post based on the provided text and feedback:', 'Here is a rewritten LinkedIn post:', 'Here is a compelling LinkedIn post:', 'Here is a rewritten LinkedIn post:','Here is a rewritten version of the text optimized for LinkedIn engagement:'
            if clean_content.startswith(unwanted_prefix):
                clean_content = clean_content[len(unwanted_prefix):].strip()
            clean_content = clean_content.replace("*", "\*").replace("_", "\_").replace("`", "\`").replace("[", "\[")
            post_text = f"Post {i+1} (Tone: {post['tone'].capitalize()})\n\n{clean_content}"
            # Removed the sources section
            await update.message.reply_text(post_text)
        await update.message.reply_text(
            "What would you like to do next?\n"
            "- Ask me questions about these posts\n"
            "- Use /upload_linkedin to publish a post\n"
            "- Use /new to create different posts\n"
            "- Use /tone to change the tone"
        )
    except Exception as e:
        logger.error(f"Error in process_content: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Error generating posts: {str(e)}")
    USER_STATES[update.effective_user.id] = State.IDLE
    
def main():
    """Start the bot."""
    os.makedirs('./data', exist_ok=True)
    os.makedirs('./output', exist_ok=True)
    os.makedirs('./query', exist_ok=True)
    os.makedirs('./config', exist_ok=True)
    os.makedirs('./linkedin_posts', exist_ok=True)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("tone", tone_command))
    application.add_handler(CommandHandler("upload_linkedin", upload_linkedin_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()