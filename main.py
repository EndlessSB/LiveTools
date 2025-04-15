from twitchio.ext import commands, tasks
import asyncio
import aiohttp
import os
import json
from random import randint

# Files
TOKEN_FILE = "current_token.txt"
POINTS_FILE = "points.txt"
WATCHTIME_FILE = "watchtime.txt"

# Twitch API credentials
CLIENT_ID = "[REPLACE WITH CLIENT ID]"
CLIENT_SECRET = "[REPLACE WITH CLIENT SECRET]"

TOKEN = ""
REFRESH_TOKEN = ""

# Token prompt
def prompt_for_tokens():
    global TOKEN, REFRESH_TOKEN
    choice = input("Do you want to load tokens from file? (y/n): ").lower()
    if choice == "y" and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as file:
            lines = file.readlines()
            TOKEN = lines[0].strip()
            REFRESH_TOKEN = lines[1].strip()
    else:
        TOKEN = input("Enter your access token: ").strip()
        REFRESH_TOKEN = input("Enter your refresh token: ").strip()
        save_tokens(TOKEN, REFRESH_TOKEN)

# Save tokens to file
def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w") as file:
        file.write(f"{access_token}\n{refresh_token}\n")

# Refresh token using refresh_token
async def refresh_access_token():
    global TOKEN, REFRESH_TOKEN
    token_url = "https://id.twitch.tv/oauth2/token"
    params = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                TOKEN = data['access_token']
                REFRESH_TOKEN = data.get('refresh_token', REFRESH_TOKEN)
                save_tokens(TOKEN, REFRESH_TOKEN)
                print("Access token refreshed successfully.")
            else:
                print("Token refresh failed.")
                print(await response.text())

# Load from JSON file
def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

# Save to JSON file
def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)

# Twitch Bot Class
class TwitchBot(commands.Bot):

    def __init__(self, channel):
        super().__init__(token=TOKEN, prefix='!', initial_channels=[channel])
        self.points = load_data(POINTS_FILE)
        self.watchtime = load_data(WATCHTIME_FILE)
        self.token_refresher.start()
        self.watchtime_tracker.start()

    # Refresh token every hour
    @tasks.loop(hours=1)
    async def token_refresher(self):
        await refresh_access_token()

    # Add 1 minute watchtime every minute
    @tasks.loop(minutes=1)
    async def watchtime_tracker(self):
        for user in self.watchtime:
            self.watchtime[user] += 1
            if self.watchtime[user] % 60 == 0:
                self.points[user] = self.points.get(user, 0) + 500

        save_data(WATCHTIME_FILE, self.watchtime)
        save_data(POINTS_FILE, self.points)

    async def event_ready(self):
        print(f"Logged in as | {self.nick}")

    async def event_message(self, message):
        if message.echo:
            return

        user = message.author.name

        # First-time setup
        if user not in self.watchtime:
            self.watchtime[user] = 0
        if user not in self.points:
            self.points[user] = 1000  # Starting bonus

        save_data(POINTS_FILE, self.points)
        save_data(WATCHTIME_FILE, self.watchtime)

        await self.handle_commands(message)

    @commands.command(name="credits")
    async def credits(self, ctx):
        await ctx.send(f"@{ctx.author.name} | LiveTools: Developed by EndlessSB on GitHub and Twitch!")

    @commands.command(name="points")
    async def points_cmd(self, ctx):
        points = self.points.get(ctx.author.name, 0)
        await ctx.send(f"@{ctx.author.name}, you have {points} points.")

    @commands.command(name="gamble")
    async def gamble_cmd(self, ctx):
        parts = ctx.message.content.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await ctx.send(f"@{ctx.author.name}, please specify a valid amount to gamble.")
            return

        user = ctx.author.name
        amount = int(parts[1])
        balance = self.points.get(user, 0)

        if amount <= 0 or amount > balance:
            await ctx.send(f"@{user}, you don't have enough points!")
            return

        win = randint(0, 1) == 1
        if win:
            self.points[user] += amount
            await ctx.send(f"@{user}, you won {amount} points! 🎉")
        else:
            self.points[user] -= amount
            await ctx.send(f"@{user}, you lost {amount} points. 😢")

        save_data(POINTS_FILE, self.points)

    @commands.command(name="watchtime")
    async def watchtime_cmd(self, ctx):
        time = self.watchtime.get(ctx.author.name, 0)
        await ctx.send(f"@{ctx.author.name}, you’ve watched for {time} minutes.")


# Main
if __name__ == "__main__":
    prompt_for_tokens()
    channel = input("Enter the Twitch channel to join: ").strip()
    if not TOKEN or not REFRESH_TOKEN:
        print("Tokens missing. Cannot continue.")
    else:
        bot = TwitchBot(channel)
        bot.run()
