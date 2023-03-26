# placeholder-gpt

placeholder-gpt is a Discord bot written in python that uses the OpenAI API to produce bot responses.

95% of the code for this bot was written by GPT-4, and the first version was entirely written by mimicking the [GPT-4 developer livestream](https://www.youtube.com/watch?v=outcGtbnMuQ).

This version of the bot uses a single python script (discord_bot.py) and runs on Heroku.

For this code to work, you must configure a Discord app and bot using the [Discord Developer Portal](https://discord.com/developers/applications/). 

Set DISCORD_TOKEN and OPENAI_API_KEY environment variables in your Heroku environment.

To set environment variables for your heroku environment, either use the web interface or use the heroku CLI:

```bash
heroku config:set DISCORD_TOKEN=YOUR_KEY_HERE
heroku config:set OPENAI_API_KEY=YOUR_KEY_HERE
```