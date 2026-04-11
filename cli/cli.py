#!/usr/bin/env python3
"""Riven CLI - connects to Riven API server."""

import sys
import os
import re

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GREY = "\033[90m"
RESET = "\033[0m"

BOLD = "\033[1m"
DIM = "\033[2m"

TAGLINE = "⬡ ̸S̵I̷G̴N̷A̵L̷S̴ ̷◆̷ ̷T̶O̶ ̵T̷H̷E̴ ̷V̴O̵I̶D̸ ⬡"


def print_banner():
    """Print cyberpunk ASCII art banner."""
    try:
        import pyfiglet
        result = pyfiglet.figlet_format("RIVEN", font="slant")
        print(f"{RED}{result}{RESET}")
        print(f"{' ' * 30}{RED}CODEHAMMER{RESET}")
        print()
        print(f"{CYAN}┌────────────────────────────────────────┐{RESET}")
        print(f"{CYAN}│{RESET}{MAGENTA}        {TAGLINE}{CYAN}{' ' * 10}{RESET}{CYAN}│{RESET}")
        print(f"{CYAN}└────────────────────────────────────────┘{RESET}")
    except ImportError:
        print("RIVEN")
        print("------")


def get_prompt_prefix(core_name: str) -> str:
    return f"{CYAN}Riven - {core_name}{RESET}"


def get_session_line(session_id: str) -> str:
    return f"\033[90m[{session_id[:8]}]{RESET}"


def format_output(text: str) -> str:
    """Format output: strip ANSI codes, thinking tags, show tool calls nicely."""
    if not text:
        return text
    
    # Remove ANSI escape sequences
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
    output = ansi_pattern.sub('', text)
    
    # Remove thinking tags but keep content
    output = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL)
    
    # Clean up extra whitespace
    output = re.sub(r'\n\n+', '\n', output)
    output = output.strip()
    
    return output


def print_formatted(text: str):
    """Print formatted output with tool call highlighting."""
    if not text:
        return
    
    # Process to find tool calls and format them
    lines = text.split('\n')
    for line in lines:
        if '→ ' in line:
            # Tool call line - highlight it
            print(f"{YELLOW}{line}{RESET}")
        else:
            print(line)
    print()


def main():
    """Run CLI."""
    print_banner()
    
    from client import get_client
    import requests
    
    client = get_client()
    
    # Check API health
    try:
        resp = requests.get(f"{client.base_url}/")
        if resp.status_code != 200:
            print(f"{RED}Error: API not responding correctly{RESET}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"{RED}Error: Cannot connect to API at {client.base_url}{RESET}")
        print("Make sure the Riven API server is running:")
        print(f"  python -m uvicorn api:app")
        sys.exit(1)
    
    # Create session
    result = client.create_session(core_name="code_hammer")
    
    if not result.get("ok"):
        print(f"{RED}Error: {result.get('message')}{RESET}")
        sys.exit(1)
    
    session = result["session_id"]
    print(f"Using core: code_hammer")
    print(f"Session: {session[:8]}")
    print("Riven agent ready. Type '/exit' to stop, '/clear' to reset session.\n")
    
    prompt_prefix = get_prompt_prefix("code_hammer")
    
    # Input loop
    try:
        while True:
            user_input = input(f"{get_session_line(session)}\n{prompt_prefix} > ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == '/exit':
                break
            
            if user_input.lower() == '/clear':
                client.close_session()
                result = client.create_session(core_name="code_hammer")
                session = result["session_id"]
                print(f"✓ Session cleared. New session: {session[:8]}")
                continue
            
            # Send message with streaming
            try:
                raw = client.stream_message(user_input)
                formatted = format_output(raw)
                if formatted:
                    print_formatted(formatted)
            except Exception as e:
                print(f"\n{RED}Error: {e}{RESET}\n")
    
    except KeyboardInterrupt:
        print("\n^C Interrupted")
    except EOFError:
        print("\nGoodbye!")
    finally:
        client.close_session()
        print("Disconnected")


if __name__ == "__main__":
    main()