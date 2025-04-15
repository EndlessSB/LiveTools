from twitchio.ext import commands
import asyncio
import requests
import aiohttp

# File where tokens will be stored
TOKEN_FILE = "current_token.txt"


# Define Client + Client Secrect
CLIENT_ID = "[REPLACE WITH CLIENT ID]"
CLIENT_SECRET = "[REPLACE WITH CLIENT SECRECT]"

# Function to read tokens from the file
def load_tokens():
    global TOKEN, REFRESH_TOKEN
    try:
        with open(TOKEN_FILE, "r") as file:
            lines = file.readlines()
            TOKEN = lines[0].strip()
            REFRESH_TOKEN = lines[1].strip()
    except FileNotFoundError:
        print(f"{TOKEN_FILE} not found. Ensure tokens are set manually or refreshed.")
        TOKEN = ""
        REFRESH_TOKEN = ""

# Function TO save the tokens
def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w") as file:
        file.write(f"{access_token}\n")
        file.write(f"{refresh_token}\n")

# Refresh the access token using the refresh token
async def refresh_access_token():
    global TOKEN, REFRESH_TOKEN  # Declare the variables as global
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
                # Extract new access token
                new_access_token = data['access_token']
                new_refresh_token = data.get('refresh_token', REFRESH_TOKEN)  # Use new refresh token if provided
                # Update global variables
                TOKEN = new_access_token
                REFRESH_TOKEN = new_refresh_token
                # Save the new tokens to the file
                save_tokens(new_access_token, new_refresh_token)
                print(f"Access token refreshed successfully.")
            else:
                print(f"Failed to refresh access token: {response.status}")
                print(await response.text())




# Twitch bot class
class TwitchBot(commands.Bot):

    def __init__(self, channels=None):
        super().__init__(token=TOKEN, prefix='!', initial_channels=channels)
        self.joined_channels = set()

    # Call refresh_access_token periodically, e.g., every hour
    async def periodic_token_refresh(self):
        while True:
            await asyncio.sleep(3600)  # Refresh every hour
            await refresh_access_token()  # Refresh the token

    @commands.command(name="credits")
    async def credits(self, ctx):
        await ctx.send("This Example was made by TheSagess on github and discord [TheSages on Twitch]


# Main function
if __name__ == "__main__":
    load_tokens()  # Load tokens from the file at startup
    if not TOKEN or not REFRESH_TOKEN:
        print("Tokens are missing. Please ensure they are refreshed or set manually.")
    else:
        bot = TwitchBot(channels=[])  # Specify channels to initially join if needed
        bot.run()
