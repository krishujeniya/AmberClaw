import os
import sys
import json
from pathlib import Path
import subprocess

def print_banner():
    banner = """
    ============================================================
      🔱  A M B E R C L A W   P R O F E S S I O N A L  🔱
    ============================================================
      Unified AI Architecture - Local First - Production Grade
    ============================================================
    """
    print(f"\033[1;33m{banner}\033[0m")

def prompt(query, default=None, is_secret=False):
    default_text = f" [{default}]" if default else ""
    user_input = input(f"\033[1;36m? {query}{default_text}:\033[0m ").strip()
    return user_input if user_input else default

def main():
    print_banner()

    config_dir = Path.home() / ".AmberClaw"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Production-grade base config
    config_data = {
        "agents": {
            "defaults": {
                "workspace": str(Path.home() / ".amberclaw" / "workspace"),
                "model": "gemini-2.0-flash",
                "provider": "gemini",
                "temperature": 0.1
            }
        },
        "providers": {
            "gemini": {"api_key": ""},
            "openai": {"api_key": ""},
            "vllm": {"api_key": "local-dev", "api_base": "http://localhost:11434/v1"}
        },
        "assistant": {
            "enabled": True,
            "model": "gemini-2.0-flash"
        },
        "db_path": str(config_dir / "amberclaw.db")
    }

    # --- Step 1: Primary Intelligence ---
    print("\n\033[1;34m[ 🧠 Step 1: Intelligence Core ]\033[0m")
    print("  1) Google Gemini (Cloud - Recommended)")
    print("  2) Local Llama / Ollama (100% Local)")
    print("  3) OpenAI (Cloud)")
    print("  4) Manual / Skip")
    
    choice = prompt("Select your primary AI engine", default="1")

    if choice == "1":
        key = prompt("Enter Google API Key (GEMINI_API_KEY)")
        if key:
            config_data["providers"]["gemini"]["api_key"] = key
            config_data["agents"]["defaults"]["provider"] = "gemini"
            config_data["agents"]["defaults"]["model"] = "gemini/gemini-1.5-pro"
            config_data["assistant"]["model"] = "gemini-2.0-flash"
        print("  \033[1;32m✓ Intelligence: Google Gemini Configured\033[0m")
    
    elif choice == "2":
        url = prompt("Local endpoint URL", default="http://localhost:11434/v1")
        model = prompt("Local model name", default="llama3:latest")
        config_data["providers"]["vllm"]["api_base"] = url
        config_data["agents"]["defaults"]["provider"] = "vllm"
        config_data["agents"]["defaults"]["model"] = f"vllm/{model}"
        config_data["assistant"]["model"] = model
        print("  \033[1;32m✓ Intelligence: Local Llama (vLLM) Configured\033[0m")

    elif choice == "3":
        key = prompt("Enter OpenAI API Key")
        if key:
            config_data["providers"]["openai"]["api_key"] = key
            config_data["agents"]["defaults"]["provider"] = "openai"
            config_data["agents"]["defaults"]["model"] = "gpt-4o"
            config_data["assistant"]["model"] = "gpt-4o-mini"
        print("  \033[1;32m✓ Intelligence: OpenAI Configured\033[0m")

    # --- Step 2: Environment Optimization ---
    print("\n\033[1;34m[ 📁 Step 2: Workspace & Persistence ]\033[0m")
    workspace = prompt("AmberClaw Workspace Path", default=config_data["agents"]["defaults"]["workspace"])
    db_path = prompt("Database Path (Local Store)", default=config_data["db_path"])
    
    config_data["agents"]["defaults"]["workspace"] = str(Path(workspace).expanduser())
    config_data["db_path"] = str(Path(db_path).expanduser())

    # --- Step 3: Deployment ---
    print("\n\033[1;34m[ 📦 Step 3: Professional Deployment ]\033[0m")
    
    # Save to config file
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)
    
    print(f"\n\033[1;32m✓ AmberClaw configuration locked: {config_file}\033[0m")

    sync_deps = prompt("Sync local environment with 'uv'? (y/n)", default="y")
    if sync_deps.lower() == 'y':
        print("\033[1;36mSyncing via UV...\033[0m")
        subprocess.run(["uv", "sync"], check=False)
        print("\033[1;32mLocal environment synchronized.\033[0m")

    print("\n\033[1;32mAmberClaw Professional Setup Complete.\033[0m")
    print("Run \033[1;34mamberclaw --help\033[0m to explore the terminal interface.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[1;31mSetup Aborted.\033[0m")
        sys.exit(0)
