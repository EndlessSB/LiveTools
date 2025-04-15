from twitchio.ext import commands
import asyncio
import aiohttp
import os
import json
from random import randint
from datetime import datetime

# Files
TOKEN_FILE = "current_token.txt"
POINTS_FILE = "points.txt"
WATCHTIME_FILE = "watchtime.txt"

# Twitch API credentials
CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secrect"

TOKEN = ""
REFRESH_TOKEN = ""

HELIX_URL = "https://api.twitch.tv/helix"


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

def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w") as file:
        file.write(f"{access_token}\n{refresh_token}\n")

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

async def get_user_id(username):
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {TOKEN}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{HELIX_URL}/users", headers=headers, params={"login": username}) as response:
            if response.status != 200:
                print(f"Failed to fetch user ID for {username}")
                return None
            data = await response.json()
            if not data["data"]:
                return None
            return data["data"][0]["id"]

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)

class TwitchBot(commands.Bot):

    def __init__(self, channel):
        super().__init__(token=TOKEN, prefix='!', initial_channels=[channel])
        self.points = load_data(POINTS_FILE)
        self.watchtime = load_data(WATCHTIME_FILE)

    async def event_ready(self):
        print(f"Logged in as | {self.nick}")
        self.loop.create_task(self.token_refresher())
        self.loop.create_task(self.watchtime_tracker())

    async def token_refresher(self):
        while True:
            await asyncio.sleep(3600)
            await refresh_access_token()

    async def watchtime_tracker(self):
        while True:
            await asyncio.sleep(60)
            for user in self.watchtime:
                self.watchtime[user] += 1
                if self.watchtime[user] % 60 == 0:
                    self.points[user] = self.points.get(user, 0) + 500
            save_data(WATCHTIME_FILE, self.watchtime)
            save_data(POINTS_FILE, self.points)

    async def event_message(self, message):
        if message.echo:
            return

        user = message.author.name

        if user not in self.watchtime:
            self.watchtime[user] = 0
        if user not in self.points:
            self.points[user] = 1000

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

    @commands.command(name="followage")
    async def followage(self, ctx):
        username = ctx.author.name
        streamer = ctx.channel.name

        user_id = await get_user_id(username)
        streamer_id = await get_user_id(streamer)

        if not user_id or not streamer_id:
            await ctx.send(f"@{ctx.author.name} | Could not fetch user IDs.")
            return

        headers = {
            "Client-ID": CLIENT_ID,
            "Authorization": f"Bearer {TOKEN}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HELIX_URL}/users/follows",
                                   headers=headers,
                                   params={"from_id": user_id, "to_id": streamer_id}) as response:

                if response.status != 200:
                    await ctx.send(f"@{ctx.author.name} | Failed to retrieve follow info.")
                    return

                data = await response.json()
                follow_data = data.get("data")

                if not follow_data:
                    await ctx.send(f"@{ctx.author.name} | You are not following {streamer}.")
                    return

                follow_date_str = follow_data[0].get("followed_at")
                follow_date = datetime.strptime(follow_date_str, "%Y-%m-%dT%H:%M:%SZ")
                now = datetime.utcnow()
                diff = now - follow_date
                days, seconds = diff.days, diff.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60

                await ctx.send(f"@{ctx.author.name} | You've been following {streamer} for {days} days, {hours} hours, and {minutes} minutes.")

if __name__ == "__main__":
    prompt_for_tokens()
    channel = input("Enter the Twitch channel to join: ").strip()
    if not TOKEN or not REFRESH_TOKEN:
        print("Tokens missing. Cannot continue.")
    else:
        bot = TwitchBot(channel)
        bot.run()
