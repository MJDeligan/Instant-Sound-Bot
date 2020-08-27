import os
import glob
from datetime import datetime, timedelta

import discord
from discord.ext import commands
import asyncio
import json
import aiosqlite
import pydub

from token_discord import BOT_TOKEN
import bot_config

FILE_DIR = bot_config.FILE_DIR
SOUND_PLAYER_DIR = bot_config.SOUND_PLAYER_DIR
COMMAND_PREFIX = bot_config.COMMAND_PREFIX
DEFAULT_BAN_DURATION = bot_config.DEFAULT_BAN_DURATION
ERRORS = bot_config.SEND_ERROR_MESSAGES
SWITCH = bot_config.ALLOW_SWITCH_CHANNELS
ADMIN_ROLES = bot_config.ADMIN_ROLES
client = discord.Client()

#change the prefix for chatcommands, default = '.'
bot = commands.Bot(command_prefix=COMMAND_PREFIX)


#makes the bot join your voice channel, plays the sound and stays in channel
@bot.command(
    help="Takes a soundname as a required argument and play count as an optional argument.\n\
Joins your voice channel(if not already connected) and plays the requested sound\n\
Use: .play (sound name) [play count]",
    brief="Play a sound"
)
async def play(ctx, soundName : str, playCount=1):
    """
    Joins the voice channel and plays the specified sound the specified
    number of times
    ctx: the context taken from the command in discord(automatically generated)
    soundName: the name of the sound to be played
    playCount : the number of times to play the sound(optional)
    returns : None
    """
    if playCount > bot_config.MAX_PLAYCOUNT or await isBanned(ctx.guild.id, ctx.author.id):
        return
    await play_func(ctx, soundName, playCount = playCount)


@bot.command(
    help="Instantly makes the bot leave the channel you're currently in, stopping any sound that is being played",
    brief="Make the bot leave the voice channel"
)
async def leave(ctx):
    voiceClient = ctx.guild.voice_client
    if not voiceClient:
        if ERRORS: await ctx.send('```Not connected to voice or you\'re not in the right channel```')
        return
    await voiceClient.disconnect()

# send a message with the list of available sounds to the channel
@bot.command(
    help="Posts a list of all available sounds to the channel",
    brief="Posts a list of all available sounds to the channel"
)
async def list(ctx):
    sound_list = await soundList()
    if 'output' in sound_list:
        sound_list.remove('output')
    ret_string = '```List of Sounds:\n\n'+ '\n'.join(sound_list)+'```'
    await ctx.send(ret_string)

@bot.command(
    help=f"Bans a member of the guild of the text channel the command is sent to.\
Takes the name of the user to be banned as a required argument, the duration(in days, accepts fractional days like 0.5) and the reason\
as optional arguments.\nIf you want to add a reason you must also add the duration. The default ban time is set to {DEFAULT_BAN_DURATION} days\
Banned users can still continue as normal on the server but they cannot use the bot's play and leave commands\n\
Only admins and users with the correct role can use this command.\n\
For optimal results add the discriminator(the #1234 part) of the user to ban to avoid banning innocent users with the same name.\n\
Use: .ban (username) [duration] [reason]",
    brief="Bans a user from using the bots core features"
)
async def ban(ctx, user_to_ban_name: str, ban_time=DEFAULT_BAN_DURATION, reason="Unspecified"):
    if ctx.author != ctx.guild.owner and ctx.author.name != "MrGandalfAndhi" and not any(role in ADMIN_ROLES for role in ctx.author.roles):
        if ERRORS: await ctx.send("```You are not authorised to ban people. Only the admin and selected members can perform this action.```")
        return
    user_id = await get_id_from_name(ctx, user_to_ban_name)
    if user_id is None:
        return
    guild_id = ctx.guild.id
    unban_time = await calc_time_after_timedelta(ban_time)
    if await isBanned(guild_id, user_id):
        if ERRORS: await ctx.send(f"```{user_to_ban_name} is already banned```")
        return
    async with aiosqlite.connect('banned.db') as db:
        await db.execute("INSERT INTO banned_users VALUES (?,?,?,?)", (user_id, guild_id, unban_time, reason))
        await db.commit()
    await ctx.send(f"```User {user_to_ban_name} banned for {ban_time} days.```")

@bot.command(
    help="Unbans a member of the guild of the text channel the command is sent to.\n\
Takes the name of the user to be unbanned as a required argument.\n\
Only admins and users with the correct role can use this command.\n\
For optimal results add the discriminator(the #1234 part) of the user to ban to avoid banning innocent users with the same name.\n\
Use: .unban (username)",
    brief="Unbans the specified user allowing them to use the bot again"
)
async def unban(ctx, user_to_unban_name: str):
    if not has_admin_rights(ctx):
        if ERRORS: await ctx.send("```You are not authorised to unban people. Only the admin and selected members can perform this action.```")
        return
    guild_id = ctx.guild.id
    user_id = await get_id_from_name(ctx, user_to_unban_name)
    if user_id is None:
        if ERRORS: await ctx.send(f"```Could not find user {user_to_unban_name}. This command is case sensitive and the name must match exactly.```")
        return
    if not await isBanned(guild_id, user_id):
        if ERRORS: await ctx.send(f"```{user_to_unban_name} is not banned. This command is case sensitive and the name must match exactly.```")
        return
    async with aiosqlite.connect('banned.db') as db:
        del_query = "DELETE FROM banned_users WHERE guild_id = ? AND user_id = ?"
        await db.execute(del_query, (guild_id, user_id))
        await db.commit()
    await ctx.send(f"```{user_to_unban_name} has been unbanned```")

# get the ban status of a user (named)
@bot.command(
    help="Checks the status of the ban of the specified user\n\
Shows the remaining time of the ban and the reason for the ban\n\
Use: .banStatus (username)",
    brief="Check the ban status of a user"
)
async def banStatus(ctx, user_name: str):
    user_id = await get_id_from_name(ctx, user_name)
    if not user_id:
        if ERRORS: await ctx.send(f"```Could not find user {user_name}. This command is case sensitive and the name must match exactly.```")
        return
    if not await isBanned(ctx.guild.id, user_id):
        await ctx.send("```Status:\nNot Banned```")
        return
    else:
        async with aiosqlite.connect('banned.db') as db:
            query = "SELECT * FROM banned_users WHERE guild_id = ? AND user_id = ?"
            cursor = await db.execute(query, (ctx.guild.id, user_id))
            user_info = await cursor.fetchone()
            unban_time, reason = user_info[2:]
            t = unban_time - int(datetime.now().timestamp())
            td = timedelta(seconds=t)
            days = td.days
            seconds = td.seconds
            hours, minutes, seconds = await convert_seconds(seconds)
            time_string = f"{days} days {hours} hours {minutes} minutes {seconds} seconds"
            await ctx.send(f"```Status:\nBanned\n\nTime until unban:\n{time_string}\n\nReason:\n{reason}```")

async def has_admin_rights(ctx):
    isAdmin = ctx.author == ctx.guild.owner
    isMe = ctx.author.name == "MrGandalfAndhi"
    hasRole = any(role in ADMIN_ROLES for role in ctx.author.roles)
    return isAdmin or isMe or hasRole


# gets the list of all the mp3 files in the file directory
# Sounds folder needs to exist, otherwise this crashes
async def soundList():
    try:
        soundList = glob.glob(FILE_DIR + '/*.mp3')
    except:
        soundList = []
    adjustedNamesList = [sound[len(FILE_DIR) + 1:-4] for sound in soundList]
    return adjustedNamesList

async def get_id_from_name(ctx, name: str):
    member_object = ctx.guild.get_member_named(name)
    if not member_object:
        if ERRORS: await ctx.send(f"```User {name} was not found. This command is case sensitive and the name must match exactly```")
        return None
    return member_object.id

async def calc_time_after_timedelta(days):
    td = timedelta(days=days)
    now = datetime.now()
    datetime_after_timedelta = now + td
    return int(datetime_after_timedelta.timestamp())

async def convert_seconds(seconds):
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return (hours, minutes, seconds)

async def isBanned(guild_id, user_id):
    async with aiosqlite.connect('banned.db') as db:
        query = "SELECT unban_time FROM banned_users WHERE guild_id = ? AND user_id = ?"
        async with db.execute(query, (guild_id, user_id)) as cursor:
            result = await cursor.fetchone()
            if not result:
                return False
            # ban has expired
            elif datetime.now().timestamp() >= result[0]:
                query = "DELETE FROM banned_users WHERE guild_id = ? AND user_id = ?"
                await db.execute(query, (guild_id, user_id))
                await db.commit()
                return False
            else:
                return True

async def getVoiceClient(ctx):
    user_voice = ctx.author.voice
    bot_voice = ctx.guild.voice_client
    # user is in voice channel
    if user_voice:
        # there is no established connection to voice channel for the bot
        if not bot_voice:
            voice_client = await user_voice.channel.connect()
        # bot and user are not connected to the same voice channel
        elif user_voice.channel.id != bot_voice.channel.id:
            # if the bot is set to switch channels when needed
            if SWITCH:
                await bot_voice.disconnect()
                voice_client = await user_voice.channel.connect()
            # bot is not allowed to switch and we should return None to indicate we cannot connect
            else:
                voice_client = None
        # the bot is connected to the same channel as the user
        else:
            voice_client = bot_voice
    else:
        voice_client = None
    return voice_client

async def play_func(ctx, soundName: str, playCount = 1):
    """
    Joins the voice channel and plays the specified sound the specified
    number of times
    ctx: the context taken from the command in discord(automatically generated)
    soundName: the name of the sound to be played
    playCount : the number of times to play the sound(optional)
    returns : None
    """
    playCount = int(playCount)
    if playCount > bot_config.MAX_PLAYCOUNT:
        if ERRORS: await ctx.send(f"```Please do not spam. The maximum amount of plays is set to {bot_config.MAX_PLAYCOUNT}```")
    SoundList = await soundList()
    if soundName not in SoundList:
        if ERRORS: await ctx.send(f'```Couldn\'t find a sound named {soundName} in your \'Sounds\'-folder```')
        return
    # get voiceclient before writing to file to check if bot is already playing from file
    # otherwise we can't queue sounds because we'd have to allow allow writing to files being played
    voiceClient = await getVoiceClient(ctx)
    if not voiceClient:
        err_msg = '```Error, you might not be connected to a voice channel or you are in a different channel and the bot is set to not switch```'
        if ERRORS: await ctx.send(err_msg)
        return
    # wait while bot is playing another sound
    # allows for queuing of sounds 
    while voiceClient.is_playing():
        await asyncio.sleep(0.1)
    soundName = FILE_DIR + "/" + soundName + '.mp3'
    with open(FILE_DIR + "/output.mp3", "wb") as outputFile, \
         open(soundName, "rb") as fileToCopy:
        binaryData = fileToCopy.read()
        #writes the sound binary data into outputfile "playCount" times
        multipliedBinaryData = playCount*binaryData
        outputFile.write(multipliedBinaryData)
    #create a new playable audiosource from the soundfile
    audioSource = discord.FFmpegPCMAudio(
        FILE_DIR+"/output.mp3",
        executable = SOUND_PLAYER_DIR
        )
    #get the voiceClient
    voiceClient.play(audioSource)
    return None


async def init_db():
    db = await aiosqlite.connect('banned.db')
    await db.execute('CREATE TABLE IF NOT EXISTS banned_users (user_id, guild_id, unban_time, reason)')
    await db.commit()
    return

asyncio.run(init_db())
bot.run(BOT_TOKEN)

