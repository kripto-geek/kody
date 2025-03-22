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
import json
import requests

# Optional lenient JSON parser
try:
    import demjson
except ImportError:
    demjson = None

# ------------------------------
# Configuration & Color Codes
# ------------------------------
IGNORED_EXTENSIONS = {".jpg", ".png", ".gif", ".bmp", ".mp3", ".mp4", ".zip", ".tar", ".gz", ".pdf", ".exe", ".bin"}
IGNORED_DIRS = {"node_modules", "vendor", "dist", "build", ".venv"}

COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"

# Max character limit for file content (increased from 500)
MAX_FILE_CONTENT_CHARS = 4000
# Max number of files to include in context
MAX_FILES_IN_CONTEXT = 10
# Memory limit for total context
MAX_CONTEXT_CHARS = 25000

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
        self.spinner_thread = threading.Thread(target=self._spin)
        self.spinner_thread.start()

    def stop(self):
        self.done = True
        if self.spinner_thread.is_alive():
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

def truncate_content(content, limit=MAX_FILE_CONTENT_CHARS):
    if len(content) <= limit:
        return content

    # Smart truncation with markers
    half = limit // 2
    return content[:half] + "\n\n...[middle content omitted]...\n\n" + content[-half:]

def filter_relevant_files(project_files, instruction, target_file=None):
    """Select relevant files based on instruction and target file"""
    if not project_files:
        return {}

    # If target file is specified, always include it
    relevant_files = {}
    if target_file and target_file in project_files:
        relevant_files[target_file] = project_files[target_file]

    # Extract potential file extensions from instruction
    words = instruction.lower().split()
    potential_exts = [w for w in words if w.startswith('.') and len(w) < 6]

    # Calculate relevance score for each file
    file_scores = {}
    for filename, content in project_files.items():
        if filename in relevant_files:
            continue

        score = 0
        # Matching extension mentioned in instruction
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in potential_exts:
            score += 5

        # File name mentioned in instruction
        base_name = os.path.basename(filename).lower()
        if base_name in instruction.lower():
            score += 10

        # Give higher score to smaller files (more likely to be relevant)
        score -= min(5, len(content) // 5000)

        file_scores[filename] = score

    # Add highest scoring files until limit
    sorted_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)
    files_to_add = min(MAX_FILES_IN_CONTEXT - len(relevant_files), len(sorted_files))

    total_chars = sum(len(content) for content in relevant_files.values())
    for filename, score in sorted_files[:files_to_add]:
        if total_chars > MAX_CONTEXT_CHARS:
            break

        content = project_files[filename]
        truncated = truncate_content(content)
        relevant_files[filename] = truncated
        total_chars += len(truncated)

    return relevant_files

def build_project_prompt(project_files, instruction, target_file=None):
    # Apply smart file filtering
    relevant_files = filter_relevant_files(project_files, instruction, target_file)

    prompt = (
        "I'm working on a project and need help modifying code. Here are the relevant files:\n\n"
    )

    for filename, content in relevant_files.items():
        # Highlight target file if specified
        file_header = f"{'[TARGET] ' if filename == target_file else ''}File: {filename}"
        prompt += f"{file_header}\nContent:\n{content}\n"
        prompt += "-----------------------------\n"

    prompt += f"\nInstruction: {instruction}\n\n"

    # Enhanced instructions for preservation
    prompt += (
        "IMPORTANT GUIDELINES:\n"
        "1. PRESERVE ALL EXISTING FUNCTIONALITY when modifying files.\n"
        "2. Only change what is necessary to implement the requested feature.\n"
        "3. Be precise with your modifications.\n"
        "4. Include ALL original code in your response for any modified files.\n\n"
    )

    prompt += (
        "Return your response in valid JSON format. For modifications, use:\n"
        '{"modifications": [\n'
        '    {"filename": "<relative_path>", "new_content": "<complete file content with modifications>"},\n'
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

def build_bash_prompt(project_files, instruction):
    file_list = "\n".join(sorted(project_files.keys()))
    prompt = (
        f"Current directory files:\n{file_list}\n\n"
        f"Instruction: {instruction}\n"
        "Generate a bash command that accomplishes this task. Return only the command without any markdown formatting."
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
# AI Integration
# ------------------------------
def run_AI_command(prompt):
    try:
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        url = config['creds']['url']
        model = config['creds']['model']
        key = config['creds']['key']

        try:
            response = requests.post(
                url=f"{url}",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": f"{model}",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                })
            )
            full_response = response.json()
            result = full_response["choices"][0]['message']['content']
            return result
        except Exception as e:
            return f"Error calling AI: {e}"
    except FileNotFoundError:
        return "Error: config.json not found. Please ensure you have a valid configuration file."
    except json.JSONDecodeError:
        return "Error: config.json is not valid JSON."
    except KeyError as e:
        return f"Error: Missing required key in config.json: {e}"

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
# Smart File Selection Helper
# ------------------------------
def extract_target_file(instruction):
    """Try to determine the target file from the instruction"""
    # Common patterns like "add X to file.py" or "update file.py"
    patterns = [
        r'(?:add|modify|update|change|edit).*?(?:to|in|on|at)\s+[\'"]?([^\s\'"]+\.[a-zA-Z0-9]+)[\'"]?',
        r'[\'"]?([^\s\'"]+\.[a-zA-Z0-9]+)[\'"]?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, instruction, re.IGNORECASE)
        if matches:
            for match in matches:
                # Filter out common false positives
                if not match.startswith(('.', '/', 'http')) and '.' in match:
                    return match
    return None

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
        response = run_AI_command(prompt)
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

    def get_file(self, filename):
        """Get file content, refreshing if necessary"""
        if filename not in self.files:
            # Try to refresh this specific file
            try:
                with open(filename, 'r', encoding="utf8") as f:
                    self.files[filename] = f.read()
            except Exception:
                return None
        return self.files.get(filename)

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
# Project Update Function (Modifications & Creations)
# ------------------------------
def project_update(project_ctx, chat_session, instruction):
    # Try to identify the target file from the instruction
    target_file = extract_target_file(instruction)
    if target_file:
        # Check if the file exists in the project
        if target_file not in project_ctx.files and os.path.exists(target_file):
            # Add the file to our context if it exists but wasn't scanned
            project_ctx.get_file(target_file)

        if target_file in project_ctx.files:
            print(f"{COLOR_CYAN}Identified target file: {target_file}{COLOR_RESET}")
        else:
            print(f"{COLOR_YELLOW}Target file '{target_file}' not found. Planning to create it.{COLOR_RESET}")

    # Build the prompt with smart context management
    prompt = build_project_prompt(project_ctx.files, instruction, target_file)

    # Generate AI response
    spinner = LoadingSpinner()
    spinner.start()
    ai_response = chat_session.send_message(prompt)
    spinner.stop()

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

        # Refresh file from disk to ensure we have latest
        old_content = project_ctx.get_file(filename) or ""

        if "@@" in new_content:
            print(f"{COLOR_YELLOW}Detected diff patch for {filename}.{COLOR_RESET}")
            patched = apply_patch_with_system(filename, new_content)
            if patched is None:
                print(f"{COLOR_RED}Failed to apply patch for {filename}.{COLOR_RESET}")
                continue
            new_content = patched

        print(f"\n{COLOR_YELLOW}--- Proposed Modification for {filename} ---{COLOR_RESET}\n")

        # Only show diff preview if file exists
        if old_content:
            print(diff_preview(old_content, new_content))
        else:
            print(f"{COLOR_CYAN}New file content:{COLOR_RESET}")
            print(new_content[:500] + ("..." if len(new_content) > 500 else ""))

        print(f"\n{COLOR_YELLOW}----------------------------------------------{COLOR_RESET}\n")

        # Safety check for destructive changes
        if old_content and len(old_content) > 100 and len(new_content) < len(old_content) * 0.5:
            print(f"{COLOR_RED}WARNING: The proposed changes significantly reduce file size.{COLOR_RESET}")
            print(f"{COLOR_RED}This might indicate destructive changes or loss of functionality.{COLOR_RESET}")

        confirm = input(f"{COLOR_GREEN}Apply these changes to {filename}? (y/n): {COLOR_RESET}").strip().lower()
        if confirm == "y":
            try:
                # Ensure directory exists
                dir_name = os.path.dirname(filename)
                if dir_name and not os.path.exists(dir_name):
                    os.makedirs(dir_name, exist_ok=True)

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
                    project_ctx.files[filename] = content
                except Exception as e:
                    print(f"{COLOR_RED}Error creating file {filename}: {e}{COLOR_RESET}")
            else:
                print(f"{COLOR_YELLOW}Creation for file {filename} cancelled.{COLOR_RESET}")

# ------------------------------
# Bash Command Generation Function
# ------------------------------
def generate_bash_command(chat_session, project_ctx, instruction):
    file_list = "\n".join(sorted(project_ctx.list_files()))
    prompt = (
        f"Current directory files:\n{file_list}\n\n"
        f"Instruction: {instruction}\n"
        "Generate a bash command that accomplishes this task. Return only the command without any markdown formatting."
    )
    response = chat_session.send_message(prompt)
    command = response.strip()
    # Remove any markdown formatting if present
    command = re.sub(r"^```bash\s*", "", command)
    command = re.sub(r"^```\s*", "", command)
    command = re.sub(r"\s*```$", "", command)
    # Display the command in a distinct, creative box.
    box_width = 60
    box_top = "┌" + "─" * box_width + "┐"
    box_bottom = "└" + "─" * box_width + "┘"
    box_content = f"│{COLOR_CYAN} Proposed Bash Command: {COLOR_RESET}\n│ {command}\n"
    separator = "│" + " " * box_width + "│"
    print(f"{COLOR_CYAN}{box_top}{COLOR_RESET}")
    print(f"{COLOR_CYAN}{box_content}{COLOR_RESET}")
    print(f"{COLOR_CYAN}{box_bottom}{COLOR_RESET}")
    confirm = input(f"{COLOR_GREEN}Execute this command? (y/n): {COLOR_RESET}").strip().lower()
    if confirm == "y":
        exec_command(command)
    else:
        print(f"{COLOR_YELLOW}Bash command execution cancelled.{COLOR_RESET}")

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
# Main Interactive Loop & Command Parsing
# ------------------------------
def print_usage():
    usage_text = f"""{COLOR_BOLD}{COLOR_CYAN}KODY - Interactive AI Project CLI Tool{COLOR_RESET}

Commands:
  {COLOR_YELLOW}chat <message>{COLOR_RESET}
      General chat with the AI.
      Example: {COLOR_GREEN}chat What do you think of my error handling?{COLOR_RESET}

  {COLOR_YELLOW}show-file <filename>{COLOR_RESET}
      Display a file's content.
      Example: {COLOR_GREEN}show-file index.html{COLOR_RESET}

  {COLOR_YELLOW}project-list{COLOR_RESET}
      List all project files.

  {COLOR_YELLOW}project-refresh{COLOR_RESET}
      Re-scan the current directory.

  {COLOR_YELLOW}project update <instruction>{COLOR_RESET}
      Update the project by modifying/creating files.
      Example: {COLOR_GREEN}project update modify the contact section in index.html to match the theme{COLOR_RESET}

  {COLOR_YELLOW}bashcmd <instruction>{COLOR_RESET}
      Ask the AI to generate a bash command to perform a task.
      Example: {COLOR_GREEN}bashcmd create a notes.txt file in current directory{COLOR_RESET}

  {COLOR_YELLOW}exec <shell command>{COLOR_RESET}
      Execute a bash command.
      Example: {COLOR_GREEN}exec ls -la{COLOR_RESET}

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

    print(f"{COLOR_GREEN}{COLOR_BOLD}KODY is ready! Type 'help' for available commands.\n{COLOR_RESET}")

    while True:
        try:
            user_input = input(f"\n{COLOR_GREEN}{COLOR_YELLOW} {COLOR_RESET}").strip()
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
                print(f"{COLOR_RED}Usage: project update <instruction>{COLOR_RESET}")
                continue
            subcmd = tokens[1].lower()
            if subcmd == "update":
                instruction = user_input.split(None, 2)[2] if len(tokens) >= 3 else ""
                if instruction:
                    project_update(project_ctx, chat_session, instruction)
                else:
                    print(f"{COLOR_RED}No update instruction provided.{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Unknown project subcommand. Use update.{COLOR_RESET}")
        elif cmd == "bashcmd":
            instruction = user_input[len("bashcmd "):].strip()
            if instruction:
                generate_bash_command(chat_session, project_ctx, instruction)
            else:
                print(f"{COLOR_RED}No instruction provided for bashcmd.{COLOR_RESET}")
        elif cmd == "exec":
            command = user_input[len("exec "):].strip()
            exec_command(command)
        else:
            print(arrow_wrap("User: " + user_input))
            response = chat_session.send_message(user_input)
            print(arrow_wrap("AI: " + response))

if __name__ == "__main__":
    main()
