#path to the directory where the mp3 files are located
#e.g FILE_DIR = "media/sounds"
FILE_DIR = "sounds"

# the path to the sound player executable
SOUND_PLAYER_DIR = "ffmpeg/bin/ffmpeg"

# the prefix for commands
COMMAND_PREFIX = "."

MAX_PLAYCOUNT = 3

# in days, also accepts decimals
DEFAULT_BAN_DURATION = 7

# set whether the bot should send messages to the channel if there is an error in the execution of the command
# e.g wrong arguments were passed or a user does not have the rights to use a command
# can be True or False
SEND_ERROR_MESSAGES = True

# set whether the bot is allowed to switch channels if a user from another channel than the bot is in
# requests it to join the channel
ALLOW_SWITCH_CHANNELS = True

# a list of roles that get the right to ban and unban people
# server admins automatically get these rights
ADMIN_ROLES = set([
    "soundadmin"
])
