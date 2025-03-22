# Kody - A Python CLI Tool

![Shot-2025-03-09-114925](https://github.com/user-attachments/assets/8b6008d2-11a9-4098-a97b-877ba2d5cc8c)

Kody is a powerful tool built to ease the use of ai in system directly. With this tool user can ask for performing codings, running bash commands and etc ai features direcly in their termninal without neeeding to copy pase or anything.

## Commands

  chat: 
      General chat with the AI.
      Example: chat What do you think of my error handling?

  show-file: 
      Display a file's content.
      Example: show-file index.html

  project-list: 
      List all project files.

  project-refresh: 
      Re-scan the current directory.

  project update: 
      Update the project by modifying/creating files.
      Example: project update make a complete flask app with any fun api.

  bashcmd:
      Ask the AI to generate a bash command to perform a task.
      Example: bashcmd create a blank notes.txt file in current directory

  exec: 
      Execute a bash command.
      Example: exec ls -la

  help or usage: 
      Show these instructions.

  exit or quit: 
      Exit KODY.

## Setup

Modify the config.json with your api key. Currently the config is setup with openrouter, So you can just go and grab the **free** openrouter key and replace your key. You can change the model based on your needs. Currently using free deepseek model (It's the one on which the tool is tested the most) 

```
git clone https://github.com/kripto-geek/kody.git
cd kody
pip install -r requirements.txt
python kody.py
```

You can set the export this tool's PATH to be accessible globally. Make sure to launch the tool in the directory where your project exist or where you want to create a project. Launching in home directory will make the tool load all unnecessary things from whole system and reach its limit.

## Contributing
Contributions are welcome! Please follow the standard fork-and-pull request workflow.

## License
Kody is open-source and available under the MIT License.

## Author
Kody was created by [Kripto-Geek] and is maintained by the community.

## Support
For support, please open an issue on the GitHub repository or reach out via email.

Happy coding with Kody! 🚀
