import os
import sys
import json
from pathlib import Path
import subprocess

def print_banner():
    banner = """
    ============================================================
      🚀 A M B E R C L A W   Q U I C K   S E T U P 
    ============================================================
      Welcome to the 1-Line Interactive Setup for AmberClaw!
      We will configure your Personal AI Assistant in seconds.
    ============================================================
    """
    print(f"\033[1;36m{banner}\033[0m")

def prompt(query, default=None, is_secret=False):
    default_text = f" [{default}]" if default else ""
    user_input = input(f"\033[1;33m? {query}{default_text}:\033[0m ").strip()
    return user_input if user_input else default

def main():
    print_banner()

    config_dir = Path.home() / ".AmberClaw"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Default base config
    config_data = {
        "channels": {
            "telegram": {"enabled": False},
            "whatsapp": {"enabled": False}
        },
        "providers": {
            "gemini": {"api_key": ""},
            "openai": {"api_key": ""}
        },
        "agents": {
            "defaults": {
                "model": "anthropic/claude-opus-4-5",
                "provider": "auto"
            }
        }
    }

    # Load existing config if it exists
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                existing_data = json.load(f)
                
                # Deep update function
                def update_dict(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict):
                            d[k] = update_dict(d.get(k, {}), v)
                        else:
                            d[k] = v
                    return d
                
                config_data = update_dict(existing_data, config_data)
        except Exception:
            pass

    # --- Step 1: Chat Integration ---
    print("\n\033[1;34m[ Step 1: Chat Integration ]\033[0m")
    print("  1) Telegram")
    print("  2) WhatsApp")
    print("  3) Skip")
    chat_choice = prompt("Select an option (1-3)", default="3")

    if chat_choice == "1":
        config_data["channels"]["telegram"]["enabled"] = True
        token = prompt("Enter your Telegram Bot Token")
        if token:
            config_data["channels"]["telegram"]["token"] = token
            # Get user ID if possible
            tg_id = prompt("Enter your Telegram User ID (Numbers only, optional)")
            if tg_id:
                config_data["channels"]["telegram"]["allowFrom"] = [tg_id]
        print("  \033[1;32m✓ Telegram Configured!\033[0m")
    elif chat_choice == "2":
        config_data["channels"]["whatsapp"]["enabled"] = True
        print("  \033[1;32m✓ WhatsApp Configured!\033[0m (Requires 'amberclaw channels login' later)")

    # --- Step 2: AI Provider Selection ---
    print("\n\033[1;34m[ Step 2: AI Provider Selection ]\033[0m")
    print("  1) Google Gemini")
    print("  2) OpenAI")
    print("  3) Skip")
    api_choice = prompt("Select an option (1-3)", default="3")

    if api_choice == "1":
        api_key = prompt("Enter your Google Gemini API Key")
        if api_key:
            config_data["providers"]["gemini"]["api_key"] = api_key
            config_data["agents"]["defaults"]["provider"] = "gemini"
            config_data["agents"]["defaults"]["model"] = "gemini/gemini-2.5-flash"
        print("  \033[1;32m✓ Google Gemini Configured!\033[0m")
    elif api_choice == "2":
        api_key = prompt("Enter your OpenAI API Key")
        if api_key:
            config_data["providers"]["openai"]["api_key"] = api_key
            config_data["agents"]["defaults"]["provider"] = "openai"
            config_data["agents"]["defaults"]["model"] = "gpt-4o"
        print("  \033[1;32m✓ OpenAI Configured!\033[0m")

    # Save to config file
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)
    
    print(f"\n\033[1;32m✓ Settings saved successfully to {config_file}\033[0m")

    # Ask to install/start
    print("\n\033[1;34m[ Step 3: Start AmberClaw ]\033[0m")
    run_now = prompt("Do you want to install and start the gateway now? (y/n)", default="y")
    if run_now.lower() == 'y':
        print("\033[1;36mInstalling via pip...\033[0m")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=False)
        print("\033[1;32mStarting AmberClaw Gateway...\033[0m")
        try:
            subprocess.run(["amberclaw", "gateway"])
        except FileNotFoundError:
            # Fallback if amberclaw is not in PATH
            subprocess.run([sys.executable, "-m", "amberclaw.cli", "gateway"])
    else:
        print("\n\033[1;32mSetup complete! To run later, use:\033[0m")
        if chat_choice == '2':
            print("  amberclaw channels login  # (To link WhatsApp)")
        print("  amberclaw gateway         # (To start the server)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[1;31mSetup Customization Aborted.\033[0m")
        sys.exit(0)
