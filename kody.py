#!/usr/bin/env python3
import os
import subprocess
import shlex
import json
import re
import difflib
import sys
import threading
import time
import tempfile

# Optional lenient JSON parser
try:
    import demjson
except ImportError:
    demjson = None

# ------------------------------
# Configuration & Color Codes
# ------------------------------
IGNORED_EXTENSIONS = {".jpg", ".png", ".gif", ".bmp", ".mp3", ".mp4", ".zip", ".tar", ".gz", ".pdf", ".exe", ".bin"}
# Also ignore these directories during scanning.
IGNORED_DIRS = {"node_modules", "vendor", "dist", "build", "images", "audio"}

COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"

# ------------------------------
# Terminal Utilities
# ------------------------------
def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

# ------------------------------
# ASCII Art Header for KODY
# ------------------------------
def print_header():
    header = f"""
{COLOR_CYAN}{COLOR_BOLD}
▄ •▄       ·▄▄▄▄   ▄· ▄▌
█▌▄▌▪▪     ██▪ ██ ▐█▪██▌
▐▀▀▄· ▄█▀▄ ▐█· ▐█▌▐█▌▐█▪
▐█.█▌▐█▌.▐▌██. ██  ▐█▀·.
·▀  ▀ ▀█▄▀▪▀▀▀▀▀•   ▀ •

Interactive AI Project CLI Tool - KODY
By - @Kripto-Geek
{COLOR_RESET}
"""
    print(header)

# ------------------------------
# Arrow Wrapper for Chat Blocks
# ------------------------------
def arrow_wrap(text):
    return "\n".join("  → " + line for line in text.splitlines())

# ------------------------------
# Loading Spinner Implementation
# ------------------------------
class LoadingSpinner:
    def __init__(self, message="Lemme Think"):
        self.message = message
        self.done = False
        self.spinner_thread = threading.Thread(target=self._spin)
        self.spinner_chars = ['|', '/', '-', '\\']

    def _spin(self):
        idx = 0
        while not self.done:
            print(f"\r{COLOR_YELLOW}{self.message}... {self.spinner_chars[idx % len(self.spinner_chars)]}{COLOR_RESET}", end='', flush=True)
            time.sleep(0.1)
            idx += 1
        print("\r" + " " * (len(self.message) + 10) + "\r", end='', flush=True)

    def start(self):
        self.done = False
        self.spinner_thread.start()

    def stop(self):
        self.done = True
        self.spinner_thread.join()

# ------------------------------
# Project Scanning Functions
# ------------------------------
def is_readable_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    return os.path.isfile(filepath) and os.access(filepath, os.R_OK) and ext not in IGNORED_EXTENSIONS

def scan_project():
    project_files = {}
    for root, dirs, files in os.walk('.'):
        # Remove ignored directories so os.walk doesn't descend into them.
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            filepath = os.path.join(root, file)
            if is_readable_file(filepath):
                rel_path = os.path.relpath(filepath, '.')
                try:
                    with open(filepath, 'r', encoding="utf8") as f:
                        project_files[rel_path] = f.read()
                except Exception:
                    continue
    return project_files

def truncate_content(content, limit=500):
    return content if len(content) <= limit else content[:limit] + "\n...[truncated]"

def build_project_prompt(project_files, instruction):
    prompt = "The following is the project structure with file paths and contents:\n\n"
    for filename, content in project_files.items():
        prompt += f"File: {filename}\nContent:\n{truncate_content(content)}\n"
        prompt += "-----------------------------\n"
    prompt += f"\nInstruction: {instruction}\n\n"
    prompt += (
        "Return your response in valid JSON format. For modifications, use:\n"
        '{"modifications": [\n'
        '    {"filename": "<relative_path>", "new_content": "<new content or diff patch>"},\n'
        "    ...\n"
        "]}\n\n"
        "For project creation, use:\n"
        '{"creations": [\n'
        '    {"filename": "<relative_path>", "content": "<file content>", "is_directory": <true/false>},\n'
        "    ...\n"
        "]}\n\n"
        "If no changes/creations are needed, return an empty JSON object with the corresponding key."
    )
    return prompt

# ------------------------------
# Diff Preview Function
# ------------------------------
def diff_preview(old, new):
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="Current",
        tofile="Proposed",
        lineterm=""
    )
    diff_text = ""
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            diff_text += f"{COLOR_GREEN}{line}{COLOR_RESET}"
        elif line.startswith('-') and not line.startswith('---'):
            diff_text += f"{COLOR_RED}{line}{COLOR_RESET}"
        elif line.startswith('@@'):
            diff_text += f"{COLOR_YELLOW}{line}{COLOR_RESET}"
        else:
            diff_text += line
    return diff_text

# ------------------------------
# Fabric Command Integration
# ------------------------------
def run_fabric_command(prompt):
    try:
        args = ["fabric", prompt]
        result = subprocess.run(args, capture_output=True, text=True)
        return result.stdout.strip() if result.stdout.strip() else result.stderr.strip()
    except Exception as e:
        return f"Error calling Fabric: {e}"

# ------------------------------
# JSON Extraction & Parsing Functions
# ------------------------------
def extract_json(response):
    response = re.sub(r"```json", "", response)
    response = re.sub(r"```", "", response)
    start = response.find('{')
    end = response.rfind('}')
    if start == -1 or end == -1:
        return None
    return response[start:end+1]

def fix_json_fields(json_str, keys=["new_content", "content"], iterations=5):
    previous = None
    for _ in range(iterations):
        if json_str == previous:
            break
        previous = json_str
        for key in keys:
            pattern = rf'("{key}":\s*")(.*?)(")'
            def replacer(match):
                prefix, content, suffix = match.group(1), match.group(2), match.group(3)
                try:
                    fixed = json.dumps(content)[1:-1]
                except Exception:
                    fixed = content
                return prefix + fixed + suffix
            json_str = re.sub(pattern, replacer, json_str, flags=re.DOTALL)
    return json_str

def try_parse_json(response):
    json_str = extract_json(response)
    if not json_str:
        raise ValueError("No JSON found in response")
    if demjson:
        try:
            return demjson.decode(json_str)
        except Exception:
            pass
    try:
        return json.loads(json_str)
    except Exception:
        fixed = fix_json_fields(json_str)
        return json.loads(fixed)

# ------------------------------
# Patch Application using system "patch" command
# ------------------------------
def apply_patch_with_system(filename, patch_text):
    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding="utf8", suffix=".patch") as temp_patch:
        temp_patch.write(patch_text)
        patch_filename = temp_patch.name
    try:
        cmd = f"patch {shlex.quote(filename)} {shlex.quote(patch_filename)}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{COLOR_RED}Patch command failed: {result.stderr}{COLOR_RESET}")
            return None
        with open(filename, "r", encoding="utf8") as f:
            updated = f.read()
        return updated
    finally:
        os.remove(patch_filename)

# ------------------------------
# Chat Session
# ------------------------------
class ChatSession:
    def __init__(self):
        self.history = ""

    def send_message(self, message):
        self.history += f"User: {message}\n"
        prompt = self.history + "AI: "
        spinner = LoadingSpinner()
        spinner.start()
        response = run_fabric_command(prompt)
        spinner.stop()
        self.history += f"{response}\n"
        return response

# ------------------------------
# Project Context
# ------------------------------
class ProjectContext:
    def __init__(self):
        self.files = scan_project()

    def refresh(self):
        self.files = scan_project()

    def list_files(self):
        return list(self.files.keys())

# ------------------------------
# File Viewing Function
# ------------------------------
def show_file(filename):
    try:
        with open(filename, "r", encoding="utf8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{filename}': {e}"

# ------------------------------
# Project Update Function (Modifications + Creations)
# ------------------------------
def project_update(project_ctx, chat_session, instruction):
    prompt = build_project_prompt(project_ctx.files, instruction)
    ai_response = chat_session.send_message(prompt)
    try:
        data = try_parse_json(ai_response)
    except Exception as e:
        print(f"{COLOR_RED}Failed to parse AI response as JSON: {e}{COLOR_RESET}")
        print("Raw response:")
        print(ai_response)
        return

    modifications = data.get("modifications", [])
    creations = data.get("creations", [])

    # Process modifications
    for mod in modifications:
        filename = mod.get("filename")
        new_content = mod.get("new_content")
        if not filename or new_content is None:
            continue
        old_content = project_ctx.files.get(filename, "")
        if "@@" in new_content:
            print(f"{COLOR_YELLOW}Detected diff patch for {filename}.{COLOR_RESET}")
            patched = apply_patch_with_system(filename, new_content)
            if patched is None:
                print(f"{COLOR_RED}Failed to apply patch for {filename}.{COLOR_RESET}")
                continue
            new_content = patched
        print(f"\n{COLOR_YELLOW}--- Proposed Modification for {filename} ---{COLOR_RESET}\n")
        print(diff_preview(old_content, new_content))
        print(f"\n{COLOR_YELLOW}----------------------------------------------{COLOR_RESET}\n")
        confirm = input(f"{COLOR_GREEN}Apply these changes to {filename}? (y/n): {COLOR_RESET}").strip().lower()
        if confirm == "y":
            try:
                with open(filename, "w", encoding="utf8") as f:
                    f.write(new_content)
                print(f"{COLOR_GREEN}{filename} updated successfully.{COLOR_RESET}")
                project_ctx.files[filename] = new_content
            except Exception as e:
                print(f"{COLOR_RED}Error writing to {filename}: {e}{COLOR_RESET}")
        else:
            print(f"{COLOR_YELLOW}Modification for {filename} cancelled.{COLOR_RESET}")

    # Process creations
    for creation in creations:
        filename = creation.get("filename")
        content = creation.get("content", "")
        is_directory = creation.get("is_directory", False)
        if not filename:
            continue
        if is_directory:
            print(f"\n{COLOR_YELLOW}--- Proposed Directory Creation: {filename} ---{COLOR_RESET}\n")
            confirm = input(f"{COLOR_GREEN}Create directory {filename}? (y/n): {COLOR_RESET}").strip().lower()
            if confirm == "y":
                try:
                    os.makedirs(filename, exist_ok=True)
                    print(f"{COLOR_GREEN}Directory {filename} created successfully.{COLOR_RESET}")
                except Exception as e:
                    print(f"{COLOR_RED}Error creating directory {filename}: {e}{COLOR_RESET}")
            else:
                print(f"{COLOR_YELLOW}Creation for directory {filename} cancelled.{COLOR_RESET}")
        else:
            print(f"\n{COLOR_YELLOW}--- Proposed File Creation: {filename} ---{COLOR_RESET}\n")
            preview = content if len(content) < 300 else content[:300] + "\n...[preview truncated]"
            print(f"{COLOR_CYAN}{preview}{COLOR_RESET}")
            print(f"\n{COLOR_YELLOW}----------------------------------------------{COLOR_RESET}\n")
            confirm = input(f"{COLOR_GREEN}Create file {filename}? (y/n): {COLOR_RESET}").strip().lower()
            if confirm == "y":
                try:
                    dir_name = os.path.dirname(filename)
                    if dir_name:
                        os.makedirs(dir_name, exist_ok=True)
                    with open(filename, "w", encoding="utf8") as f:
                        f.write(content)
                    print(f"{COLOR_GREEN}File {filename} created successfully.{COLOR_RESET}")
                except Exception as e:
                    print(f"{COLOR_RED}Error creating file {filename}: {e}{COLOR_RESET}")
            else:
                print(f"{COLOR_YELLOW}Creation for file {filename} cancelled.{COLOR_RESET}")

# ------------------------------
# Project Initialization Command
# ------------------------------
def project_init(chat_session, instruction):
    prompt = f"Provide the bash command to initialize a project with the following requirements: {instruction}. Return only the command."
    response = chat_session.send_message(prompt)
    command = response.strip()
    print(arrow_wrap("Initialization Command: " + command))
    confirm = input(f"{COLOR_GREEN}Execute this initialization command? (y/n): {COLOR_RESET}").strip().lower()
    if confirm == "y":
        exec_command(command)
    else:
        print(f"{COLOR_YELLOW}Initialization cancelled.{COLOR_RESET}")

# ------------------------------
# Command Execution Function
# ------------------------------
def exec_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else result.stderr
        print(f"\n{COLOR_CYAN}{output}{COLOR_RESET}\n")
    except Exception as e:
        print(f"{COLOR_RED}Error executing command: {e}{COLOR_RESET}")

# ------------------------------
# Main Interactive Loop
# ------------------------------
def print_usage():
    usage_text = f"""{COLOR_BOLD}{COLOR_CYAN}KODY - Interactive AI Project CLI Tool{COLOR_RESET}

Commands:
  {COLOR_YELLOW}chat <message>{COLOR_RESET}
      General conversation with the AI.
      Example: {COLOR_GREEN}chat What do you think of my error handling?{COLOR_RESET}

  {COLOR_YELLOW}show-file <filename>{COLOR_RESET}
      Display a file’s content.
      Example: {COLOR_GREEN}show-file index.html{COLOR_RESET}

  {COLOR_YELLOW}project-list{COLOR_RESET}
      List all project files.

  {COLOR_YELLOW}project-refresh{COLOR_RESET}
      Re-scan the current directory for files.

  {COLOR_YELLOW}project init <instruction>{COLOR_RESET}
      Ask the AI to provide a bash command to initialize a project (e.g., create a React app).
      Example: {COLOR_GREEN}project init create a react app helloworld{COLOR_RESET}

  {COLOR_YELLOW}project update <instruction>{COLOR_RESET}
      Update the project by modifying or creating files based on your instruction.
      Example: {COLOR_GREEN}project update modify index.html contact section to match the website theme{COLOR_RESET}

  {COLOR_YELLOW}exec <shell command>{COLOR_RESET}
      Execute a shell command.
      Example: {COLOR_GREEN}exec npm install{COLOR_RESET}

  {COLOR_YELLOW}help{COLOR_RESET} or {COLOR_YELLOW}usage{COLOR_RESET}
      Show these instructions.

  {COLOR_YELLOW}exit{COLOR_RESET} or {COLOR_YELLOW}quit{COLOR_RESET}
      Exit KODY.
"""
    print(usage_text)

def main():
    clear_terminal()
    print_header()

    chat_session = ChatSession()
    project_ctx = ProjectContext()

    while True:
        try:
            user_input = input(f"{COLOR_GREEN}{COLOR_YELLOW} {COLOR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not user_input:
            continue

        tokens = user_input.split()
        cmd = tokens[0].lower()

        if cmd in {"exit", "quit"}:
            print("Goodbye!")
            break
        elif cmd in {"help", "usage"}:
            print_usage()
            continue
        elif cmd == "chat":
            message = user_input[len("chat "):].strip()
            print(arrow_wrap("User: " + message))
            response = chat_session.send_message(message)
            print(arrow_wrap("AI: " + response))
        elif cmd == "show-file":
            filename = user_input[len("show-file "):].strip()
            content = show_file(filename)
            print("\n" + arrow_wrap(content) + "\n")
        elif cmd == "project-list":
            files = project_ctx.list_files()
            listing = "\n".join(" - " + f for f in files)
            print("\n" + arrow_wrap("Project Files:\n" + listing) + "\n")
        elif cmd == "project-refresh":
            project_ctx.refresh()
            print(f"{COLOR_GREEN}Project context refreshed. Total files: {len(project_ctx.files)}{COLOR_RESET}")
        elif cmd == "project":
            if len(tokens) < 2:
                print(f"{COLOR_RED}Usage: project init|update ...{COLOR_RESET}")
                continue
            subcmd = tokens[1].lower()
            if subcmd == "init":
                instruction = user_input.split(None, 2)[2] if len(tokens) >= 3 else ""
                if instruction:
                    project_init(chat_session, instruction)
                else:
                    print(f"{COLOR_RED}No initialization instruction provided.{COLOR_RESET}")
            elif subcmd == "update":
                instruction = user_input.split(None, 2)[2] if len(tokens) >= 3 else ""
                if instruction:
                    project_update(project_ctx, chat_session, instruction)
                else:
                    print(f"{COLOR_RED}No update instruction provided.{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Unknown project subcommand. Use init or update.{COLOR_RESET}")
        elif cmd == "modify-project" or cmd == "create-project":
            # For backward compatibility, treat them as project update.
            instruction = user_input.split(None, 1)[1] if len(tokens) > 1 else ""
            if instruction:
                project_update(project_ctx, chat_session, instruction)
            else:
                print(f"{COLOR_RED}No instruction provided.{COLOR_RESET}")
        elif cmd == "exec":
            command = user_input[len("exec "):].strip()
            exec_command(command)
        else:
            # Fallback to general chat.
            print(arrow_wrap("User: " + user_input))
            response = chat_session.send_message(user_input)
            print(arrow_wrap("AI: " + response))

if __name__ == "__main__":
    main()
