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

Modify json values in the bot_settings.txt file to match your needs. Here are some definitions from the OpenAI API reference guide:

* **temperature** _[number|optional|defaults to 1]_ What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. We generally recommend altering this or top_p but not both.
* **top_p** _[number|optional|defaults to 1]_ An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered. We generally recommend altering this or temperature but not both.
* **presence_penalty** _[number|optional|defaults to 0]_ Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics.
* **frequency_penalty** _[number|optional|defaults to 0]_ Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.
