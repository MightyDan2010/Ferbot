import discord
from discord import app_commands
from cryptography.fernet import Fernet, InvalidToken
import base64
import json
import os
import io

TOKEN = os.environ["BOT_TOKEN"]
MASTER_KEY = os.environ["MASTER_KEY"].encode()
f_master = Fernet(MASTER_KEY)
KEY_FILE = "Documents/Ferbot/UserKeys.json"
MAX_LENGTH = 2000
MAX_FILE_SIZE = 26214400

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "r") as f:
        encrypted_data = json.load(f)
        user_keys = {uid: f_master.decrypt(key.encode()).decode() for uid, key in encrypted_data.items()}
else:
    user_keys = {}
    
def save_keys():
    encrypted_data = {uid: f_master.encrypt(key.encode()).decode() for uid, key in user_keys.items()}
    with open(KEY_FILE, "w") as f:
        json.dump(encrypted_data, f)
def is_valid_fernet_key(key: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(key)
        return len(decoded) == 32
    except Exception:
        return False

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}. Bot is ready!")

@tree.command(name="encrypt", description="Encrypt a message")
@app_commands.describe(message="Your message", key="Fernet key (optional)", recipient="Addressee (server only)")
async def encode(interaction: discord.Interaction, message: str, key: str = None, recipient: discord.User = None):
    key = key or user_keys.get(str(interaction.user.id))
    if not key:
        await interaction.response.send_message("No key provided and no saved key found. Use /savekey or provide a key.", ephemeral=True)
        return
    f = Fernet(key.encode())
    encrypted_message = f.encrypt(message.encode()).decode()
    
    if len(encrypted_message) > MAX_LENGTH:
        await interaction.response.send_message("Failed to encrypt. Max message length for encryption is ~1443 ASCII characters. Using emojis or other Unicode characters reduces this limit.", ephemeral=True)
    else:
        if interaction.guild is None or recipient is None:
            await interaction.response.send_message(f"Encrypted message:\n{encrypted_message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Sending encrypted message to {recipient.name}...", ephemeral=True)
            try:
                await recipient.send(encrypted_message)
                await interaction.followup.send(f"Message successfully delivered to {recipient.name}!", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Failed to send DM. The recipient must share a server with the bot and allow DMs.\nError: {e}", ephemeral=True)
    
@tree.command(name="decrypt", description="Decrypt a message")
@app_commands.describe(encrypted_message="Encrypted message", key="Fernet key (optional)")
async def decode(interaction: discord.Interaction, encrypted_message: str, key: str = None):
    key = key or user_keys.get(str(interaction.user.id))
    if not key:
        await interaction.response.send_message("No key provided and no saved key found. Use /savekey or provide a key.", ephemeral=True)
        return
    try:
        f = Fernet(key.encode())
        decrypted_message = f.decrypt(encrypted_message.encode()).decode()
        await interaction.response.send_message(f"Decrypted message:\n{decrypted_message}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to decrypt: {e}", ephemeral=True)
        
@tree.command(name="makekey", description="Create a key consisting of 32 url-safe base64-encoded bytes")
async def makekey(interaction: discord.Interaction):
    try:
        key = Fernet.generate_key()
        await interaction.response.send_message(f"Here’s your new key:\n{key.decode()}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error:\n {e}", ephemeral=True)
        
@tree.command(name="savekey", description="Save your encryption key for later use")
@app_commands.describe(key="Fernet key")
async def savekey(interaction: discord.Interaction, key: str):
    if not is_valid_fernet_key(key):
            await interaction.response.send_message("Invalid key! A valid Fernet key must be 32 bytes (URL-safe base64).", ephemeral=True)
            return
    user_keys[str(interaction.user.id)] = key
    save_keys()
    await interaction.response.send_message("Your key has been saved!", ephemeral=True)

@tree.command(name="mykey", description="Show your saved encryption key")
async def mykey(interaction: discord.Interaction):
    key = user_keys.get(str(interaction.user.id))
    if key:
        await interaction.response.send_message(f"Your saved key:\n{key}", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have a saved key. Use /savekey to store one.", ephemeral=True)

@tree.command(name="resetkey", description="Delete your saved key")
async def resetkey(interaction: discord.Interaction):
    if str(interaction.user.id) in user_keys:
        del user_keys[str(interaction.user.id)]
        save_keys()
        await interaction.response.send_message("Your saved key has been deleted.", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have a saved key.", ephemeral=True)

@tree.command(name="encryptfile", description="Encrypt an attached file")
@app_commands.describe(file="Your file", key="Fernet key (optional)", recipient="Addressee (server only)")
async def encryptfile(interaction: discord.Interaction, file: discord.Attachment, key: str = None, recipient: discord.User = None):
    if file.size > MAX_FILE_SIZE:
        await interaction.response.send_message("Failed to encrypt. Discord limits bot file uploads to 25MB.", ephemeral=True)
        return
    key = key or user_keys.get(str(interaction.user.id))
    if not key:
        await interaction.response.send_message("No key provided and no saved key found. Use /savekey or provide a key.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        file_bytes = await file.read()
        f = Fernet(key.encode())
        encrypted_bytes = f.encrypt(file_bytes)
        encrypted_file = discord.File(fp=io.BytesIO(encrypted_bytes), filename=f"encrypted_{file.filename}.fernet")
        if interaction.guild is None or recipient is None:
            await interaction.followup.send("Encrypted file:\n", file=encrypted_file, ephemeral=True)
        else:
            awaitinteraction.followup.send(f"Sending encrypted file to {recipient.name}...", ephemeral=True)
            try:
                await recipient.send(file=encrypted_file)
                await interaction.followup.send(f"File successfully delivered to {recipient.name}!", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Failed to send DM. The recipient must share a server with the bot and allow DMs.\nError: {e}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to encrypt file:\n {e}", ephemeral=True)
        
@tree.command(name="decryptfile", description="Decrypt an attached file")
@app_commands.describe(file="Encrypted file", key="Fernet key (optional)")
async def decryptfile(interaction: discord.Interaction, file: discord.Attachment, key: str = None):
    if file.size > MAX_FILE_SIZE:
        await interaction.response.send_message("Failed to decrypt. Discord limits bot file uploads to 25MB.", ephemeral=True)
        return
    key = key or user_keys.get(str(interaction.user.id))
    if not key:
        await interaction.response.send_message("No key provided and no saved key found. Use /savekey or provide a key.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        encrypted_bytes = await file.read()
        f = Fernet(key.encode())
        decrypted_bytes = f.decrypt(encrypted_bytes)
        original_name = file.filename.replace("encrypted_", "").replace(".fernet", "")
        if not original_name:
            original_name = "decrypted_file"
        decrypted_file = discord.File(fp=io.BytesIO(decrypted_bytes), filename=original_name)
        await interaction.followup.send("Decrypted file:\n", file=decrypted_file, ephemeral=True)
    except InvalidToken:
        await interaction.followup.send("Failed to decrypt. Invalid key, corrupted file or a wrong file format (.fernet expected).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to decrypt file:\n {e}", ephemeral=True)
        
@tree.command(name="help", description="Get a list of available commands")
async def help(interaction: discord.Interaction):
        await interaction.response.send_message("/encrypt – Encrypt a message using the saved key or a custom key. optionally DM someone the message.\n\n/decrypt – Decrypt a message using the saved key or a custom key.\n\n/makekey – Generate a new 32-byte key (URL-safe base64).\n\n/savekey – Save a key to make decoding and encoding faster and easier.\n\n/mykey – View the saved key.\n\n/resetkey – Reset/delete the saved key.\n\n/encryptfile – Encrypt a file using the saved key or a custom key. optionally DM someone the file.\n\n/decryptfile – Decrypt a file using the saved key or a custom key.", ephemeral=True)
        
client.run(TOKEN)
