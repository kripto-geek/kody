# Kody - A Python CLI Tool

Kody is a powerful tool built to ease the use of ai in system directly. With this tool user can ask for performing codings, running bash commands and etc ai features direcly in their termninal without neeeding to copy pase or anything.
Kody is just a wrap for fabric tool, therefore it needs the fabric tool (https://github.com/danielmiessler/fabric).

## Commands

  chat <message>
      General chat with the AI.
      Example: chat What do you think of my error handling?

  show-file <filename>
      Display a file's content.
      Example: show-file index.html

  project-list
      List all project files.

  project-refresh
      Re-scan the current directory.

  project update <instruction>
      Update the project by modifying/creating files.
      Example: project update make a complete flask app with any fun api.

  bashcmd <instruction>
      Ask the AI to generate a bash command to perform a task.
      Example: bashcmd create a blank notes.txt file in current directory

  exec <shell command>
      Execute a bash command.
      Example: exec ls -la

  help or usage
      Show these instructions.

  exit or quit
      Exit KODY.

## Setup
To use Kody, firstly install the fabric tool.
Check out fabric's github page for your proeferred way of installation and setup: https://github.com/danielmiessler/fabric

Or if you wish you can download it directly from source (golang) : go install github.com/danielmiessler/fabric@latest

Next is to setup fabric with your ai model: thorugh fabric --setup

Once your fabric thig is done: 
Install the tool:
```
git clone https://github.com/kripto-geek/kody.git
cd kody
python kody.py
```

You can set the export this tool's PATH to be accessible globally. Make sure to launch the tool in the directory where your project exist or where you want to create a project. Launching in home directory will make the tool load all unnecessary things from whole system and reach its limit.

## Contributing
Contributions are welcome! Please follow the standard fork-and-pull request workflow.

## License
Kody is open-source and available under the MIT License.

## Author
Kody was created by [Kripto-Geek] and is maintained by the community.
But the Fabric is backbone of it (Therefore I am Greatfull and special thanks to their creator)

## Support
For support, please open an issue on the GitHub repository or reach out via email.

Happy coding with Kody! 🚀
