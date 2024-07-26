import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Replace with your bot token
BOT_TOKEN = '6950414850:AAEHbTUNz9myQDeGRDB1Dmf0jwnDy_PDgcM'

# Define the start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat.id
    # Respond with the user's chat ID
    await update.message.reply_text(f'Your chat ID is: {chat_id}')

# Main function to initialize and run the bot
def main():
    # Initialize the bot application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Define command handlers
    application.add_handler(CommandHandler('start', start))

    # Start the bot
    application.run_polling()

# Entry point for the script
if __name__ == '__main__':
    # Run the main function
    asyncio.run(main())
