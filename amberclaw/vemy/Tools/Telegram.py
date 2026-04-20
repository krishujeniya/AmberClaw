"""
Telegram Tool
Handles Telegram bot interactions and user communication
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from amberclaw.vemy.AI.Chat_Handler import ChatService
from amberclaw.vemy.Credentials.Settings import Config


class TelegramService:
    """Telegram Tool - Bot interface for user interactions"""
    
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        self.application = None
        
    async def check_authorization(self, update: Update) -> bool:
        """Check if user is authorized"""
        if not Config.AUTHORIZED_USER_ID:
            return True
        
        user_id = str(update.effective_user.id)
        return user_id == Config.AUTHORIZED_USER_ID
    
    async def start_command(self, update: Update, context):
        """Handle /start command"""
        if not await self.check_authorization(update):
            await update.message.reply_text("🔒 Sorry, this bot is private and only available to authorized users.")
            return
        
        welcome_message = """👋 Hello! I'm Vemy, your AI assistant!

I can help you with:
• Answering questions
• Providing information
• Having conversations
• And much more!

Just send me a message and I'll respond! 😊

💡 Tip: Say 'bye', 'exit', or 'goodbye' to end the chat and shutdown the bot."""
        
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context):
        """Handle /help command"""
        if not await self.check_authorization(update):
            await update.message.reply_text("🔒 Sorry, this bot is private and only available to authorized users.")
            return
        
        help_message = """🤖 **Vemy AI Assistant**

**Commands:**
/start - Start the bot
/help - Show this help message
/clear - Clear conversation history

**Exit Commands:**
Say 'bye', 'exit', 'quit', 'goodbye', 'stop', or 'end' to shutdown the bot

**How to use:**
Just send me any message and I'll respond!

I remember our conversations and can provide context-aware responses."""
        
        await update.message.reply_text(help_message)
    
    async def clear_command(self, update: Update, context):
        """Handle /clear command"""
        if not await self.check_authorization(update):
            await update.message.reply_text("🔒 Sorry, this bot is private and only available to authorized users.")
            return
        
        try:
            if self.chat_service.clear_history():
                await update.message.reply_text("✅ Conversation history cleared!")
            else:
                await update.message.reply_text("⚠️ Chat memory not available")
        except Exception as e:
            await update.message.reply_text(f"❌ Error clearing history: {e}")
    
    async def handle_message(self, update: Update, context):
        """Handle incoming messages"""
        try:
            if not await self.check_authorization(update):
                await update.message.reply_text("🔒 Sorry, this bot is private and only available to authorized users.")
                print(f"⚠️  Unauthorized access attempt from user {update.effective_user.id}")
                return
            
            chat_id = update.effective_chat.id
            user_message = update.message.text
            user_name = update.effective_user.first_name or "User"
            
            print(f"📩 Message from {user_name} ({chat_id}): {user_message}")
            
            # Check for exit commands
            exit_commands = ['bye', 'exit', 'quit', 'goodbye', 'stop', 'end']
            if user_message.lower().strip() in exit_commands:
                farewell_message = """👋 Goodbye! It was nice chatting with you!

The bot is now shutting down. To start again, just run the program.

Take care! 😊"""
                await update.message.reply_text(farewell_message)
                print(f"\n{'='*60}")
                print("👋 User said goodbye - Shutting down bot...")
                print(f"{'='*60}\n")
                
                context.application.stop_running()
                return
            
            # Send typing indicator
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Process message with chat service
            response = self.chat_service.process_message(user_message)
            
            # Send response
            await update.message.reply_text(response)
            print(f"✅ Response sent to {user_name}")
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            await update.message.reply_text(error_msg)
            print(f"❌ Error handling message: {e}")
    
    def setup(self):
        """Setup Telegram bot"""
        if not Config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        print("✅ Telegram bot configured")
        return True
    
    def run(self):
        """Run the Telegram bot"""
        if not self.application:
            raise RuntimeError("Bot not setup. Call setup() first.")
        
        print("✅ Telegram bot is running!")
        print("   Send a message to your bot to start chatting")
        print("   User can say 'bye', 'exit', or 'goodbye' to shutdown")
        print("   Or press Ctrl+C to stop")
        print()
        
        from telegram import Update
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
