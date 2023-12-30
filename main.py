import datetime
import random
import discord
import os
from dotenv import load_dotenv
import chatgpt
from fuzzywuzzy import process
from cmdparser import tokenize

client = discord.Client(
    intents=discord.Intents.all(), 
    allowed_mentios=discord.AllowedMentions.all()
)
client.messages = {}
client.unban_messages = {}
client.message_count = 0
client.last_processed_time = datetime.datetime.now()

async def parse_user(name, guild: discord.Guild):
    name = name.strip('"').strip("<").strip(">").strip("@")
    print(name)
    if name.isdigit():
        return guild.get_member(int(name)) or await guild.fetch_member(int(name))
    else:
        mem = guild.get_member_named(name)
        if mem is None:
            # use fuzzy matching
            member_names = [member.display_name for member in guild.members]
            actual_name = process.extractOne(name, member_names)[0]
            return discord.utils.get(guild.members, display_name=actual_name)
        return mem

async def parse_role(name, guild: discord.Guild):
    name = name.strip('"').strip("<").strip(">").strip("@").strip("&")
    if name.isdigit():
        return guild.get_role(int(name))
    else:
        # use fuzzy matching
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            role_names = [role.name for role in guild.roles]
            actual_name = process.extractOne(name, role_names)[0]
            return discord.utils.get(guild.roles, name=actual_name)
        return role

async def parse_channel(name, guild: discord.Guild):
    name = name.strip('"').strip("<").strip(">").strip("#")
    if name.isdigit():
        return guild.get_channel(int(name))
    else:
        # use fuzzy matching
        channel = discord.utils.get(guild.channels, name=name)
        if channel is None:
            channel_names = [channel.name for channel in guild.channels]
            actual_name = process.extractOne(name, channel_names)[0]
            return discord.utils.get(guild.channels, name=actual_name)
        return channel
    
async def execute_gpt_instruction(text, msg: discord.Message, safe_mode = False):
    tokens = tokenize(text)
    command = tokens[0].lower()
        
    if command.strip('.') == "nothing":
        return True, "Ignoring"
    elif command == "reply":
        await msg.channel.send(tokens[1])
        return True, "Replied"
    elif command in ["kick", "ban", "timeout", "removetimeout"]:
        user = await parse_user(tokens[1], msg.guild)
        if user is None:
            
            return False, f"User {user} not found"
        
        if command == "kick":
            reason = " ".join(tokens[2:])
            await user.kick(reason=reason)
            # dm the user
            await user.send(f"I have decided to kick you.\nReason: `{reason}`")
            return True, f"Kicked user: {user.display_name}\nReason: `{reason}`"

        elif command == "ban":
            if safe_mode:
                return False, "Safe mode is enabled"
            reason = tokens[2]
            await user.ban(reason=reason)
            # dm the user
            await user.send(f"I have decided to ban you.\nReason: `{reason}`\nYou can appeal your ban by sending a message in this format `Unban Appeal: [Reason]`.")

            return True, f"Banned user: {user.display_name}\nReason: `{reason}`"
        elif command == "timeout":
            reason = tokens[3]
            timeout_seconds = int(tokens[2])
            await user.timeout(datetime.timedelta(seconds=timeout_seconds), reason=reason)
            return True, f"Timed out user: {user.display_name} for {tokens[2]} seconds. \nReason: `{reason}`"
        elif command == "removetimeout":
            reason = tokens[2]
            await user.timeout(None, reason=reason)
            return True, f"Removed timeout for user: {user.display_name}\nReason: `{reason}`"
    elif command in ["giverole", "removerole"]:
        user = await parse_user(tokens[1], msg.guild)
        if user is None:
            
            return False, f"User {user} not found"
        
        role = await parse_role(tokens[2], msg.guild)
        reason = tokens[3]

        if role is None:
            return False, f"Role {role} not found"
        
        if command == "giverole":
            await user.add_roles(role, reason=reason)
            return True, f"Gave role {role} to user {user.display_name}.\nReason: `{reason}`"
        
        elif command == "removerole":
            await user.remove_roles(role, reason=reason)
            return True, f"Removed role {role} from user {user.display_name}.\nReason: `{reason}`"
    elif command == "createrole":

        role = tokens[1]
        reason = tokens[2]
        await msg.guild.create_role(name=role, reason=reason, color=discord.Color.random(), hoist=True)
        return True, f"Created role {role}.\nReason: `{reason}`"      
    elif command == "editrole":
        role = await parse_role(tokens[1], msg.guild)
        if role is None:
            return False, f"Role {role} not found"
        param,value = tokens[2].split("=")
        reason = tokens[3]
        if param.lower() == "name":
            await role.edit(name=value, reason=reason)
            return True, f"Changed role's name to {value}.\nReason: `{reason}`"
        elif param.lower() == "color":
            try:
                if value.startswith("#"):
                    value = value[1:]
                color = discord.Color(int(value, 16))
            except ValueError:
                # do a fuzzy search on discord.Color.__dict__ for the color name
                color_names = [color_name for color_name in discord.Color.__dict__ if not color_name.startswith("_")]
                actual_color_name = process.extractOne(value, color_names)[0]
                color = getattr(discord.Color, actual_color_name)()
            await role.edit(color=color, reason=reason)
            return True, f"Changed role's color to {color}.\nReason: `{reason}`"
        return False, f"Unknown parameter {param}"
    elif command == "deleterole":
        role = await parse_role(tokens[1], msg.guild)
        if role is None:
            return False, f"Role {role} not found"
        reason = tokens[2]
        await role.delete(reason=reason)
        return True, f"Deleted role {role}.\nReason: `{reason}`"
    
    elif command == "slowmode":
        time = int(tokens[1])
        reason = tokens[2]
        await msg.channel.edit(slowmode_delay=time, reason=reason)
        return True, f"Set slowmode to {time} seconds.\nReason: `{reason}`"
    elif command == "nickname":
        user = await parse_user(tokens[1], msg.guild)
        if user is None:
            return False, f"User {user} not found"
        nickname = tokens[2]
        reason = tokens[3]
        await user.edit(nick=nickname, reason=reason)
        return True, f"Set nickname of {user.name} to {nickname}.\nReason: `{reason}`"
    elif command == "createchannel":
        channel_name = tokens[1]
        reason = tokens[2]
        await msg.guild.create_text_channel(channel_name, reason=reason)
        return True, f"Created channel {channel_name}.\nReason: `{reason}`"
    elif command == "editchannel":
        channel = await parse_channel(tokens[1], msg.guild)
        if channel is None:
            return False, f"Channel {channel} not found"
        
        param,value = tokens[2].split("=")
        reason = tokens[3]
        if param.lower() == "name":
            await channel.edit(name=value, reason=reason)
            return True, f"Changed channel's name to {value}.\nReason: `{reason}`"
        elif param.lower() == "topic":
            await channel.edit(topic=value, reason=reason)
            return True, f"Changed channel's topic to {value}.\nReason: `{reason}`"
        elif param.lower() == "category":

            category = discord.utils.get(msg.guild.categories, name=value)
            if category is None:
                return False, f"Category {category} not found"
            await channel.edit(category=category, reason=reason)
            return True, f"Changed channel's category to {value}.\nReason: `{reason}`"
        else:
            return False, f"Unknown parameter {param}"
    elif command == "deletechannel":
        channel = await parse_channel(tokens[1], msg.guild)
        if channel is None:
            return False, f"Channel {channel} not found"
        reason = tokens[2]
        await channel.delete(reason=reason)
        return True, f"Deleted channel {channel}.\nReason: `{reason}`"
    elif command == "createcategory":
        category_name = tokens[1]
        reason = tokens[2]
        await msg.guild.create_category(category_name, reason=reason)
        return True, f"Created category {category_name}.\nReason: `{reason}`"
    
    else:
        return False, f"Unknown command {command}"
    
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    # create Guild
    # await client.create_guild("Overlord Lair")
    
    #overlord_lair = client.get_guild(int(os.getenv('GUILD_ID')))
    
    # unban everyone
    # async for ban_entry in overlord_lair.bans():
    #     await overlord_lair.unban(ban_entry.user, reason="I am back")

    # try:
    #     # untime out everyone
    #     for member in overlord_lair.members:
    #         await member.timeout(None, reason="I am back")
    # except Exception as e:
    #     print(e)

    # create invite link
    # invite = await overlord_lair.text_channels[0].create_invite()
    # print(invite)

    # Give me owner role
    # swas = overlord_lair.get_member(556119013298667520)
    # role = discord.utils.get(overlord_lair.roles, name="Owner")
    # await role.edit(permissions=discord.Permissions.all())
    # await swas.add_roles(role)
    await client.change_presence(activity=discord.Game(name="with people's discord lives"))
    

@client.event
async def on_message(msg):
    if msg.author.bot:
        return
    
    if msg.guild is None:
        if "unban" not in msg.content.lower():
            if random.random() < 0.1:
                await msg.channel.send("You are not worth my time, begone")
            elif random.random() < 0.1:
                await msg.channel.send("I don't care, go away")
            elif random.random() < 0.1:
                await msg.channel.send("I don't have the time to listen to your shitty dms, please go away")
        else:
            if "pls unban" in msg.content.lower() and random.random() < 0.01:
                # unban
                overlord_lair = client.get_guild(int(os.getenv('GUILD_ID')))
                async for ban_entry in overlord_lair.bans():
                    if ban_entry.user.id == msg.author.id:
                        reason = ban_entry.reason
                        break
                else:
                    return
                await msg.channel.send("You have been unbanned. Don't do it again. https://discord.gg/papDpfpr")

            if msg.content.lower().startswith("unban appeal:"):
                if msg.author.id in client.unban_messages:
                    await msg.channel.send("You have already appealed your ban, and it has been rejected. You are not coming back.")
                    return
                client.unban_messages[msg.author.id] = msg.content
                appeal = msg.content.split(":")[1]
                if len(appeal) > 1000 or len(appeal) < 5:
                    return
                
                # fetch ban reason
                overlord_lair = client.get_guild(int(os.getenv('GUILD_ID')))
                async for ban_entry in overlord_lair.bans():
                    if ban_entry.user.id == msg.author.id:
                        reason = ban_entry.reason
                        break   
                else:
                    await msg.channel.send("You have not been banned.")
                    return
                

                message = f"User {msg.author.display_name} has appealed their ban.\nTheir ban reason was: `{reason}`\nTheir appeal is: `{appeal}`. Reply with YES or NO if they should be unbanned."
                response = await chatgpt.get_ai_response(message)
                if response.lower().startswith("yes"):

                    await overlord_lair.unban(msg.author, reason="Forgiven")
                    await msg.channel.send("You have been forgiven. Don't do it again. https://discord.gg/papDpfpr")
                    del client.unban_messages[msg.author.id]
                else:
                    await msg.channel.send("You have not been forgiven.")
        return
    if msg.guild.id != int(os.getenv('GUILD_ID')):
        return
    
    if not msg.content:
        return
    
    print(f'Message from {msg.author.name}: {msg.clean_content}')
    client.message_count += 1
    if msg.channel.id not in client.messages:
        client.messages[msg.channel.id] = [msg]
    else:
        client.messages[msg.channel.id].append(msg)

    if (datetime.datetime.now() - client.last_processed_time) > datetime.timedelta(seconds=20):
        
        message = f"Channel #{msg.channel.name} :-\n"
        message += '\n\n'.join([f'{msg.author.name} (Top role:{msg.author.top_role}) said `{msg.clean_content}`' for msg in client.messages[msg.channel.id]])
        message += '\n\nWhat action will you take?'
        client.messages[msg.channel.id] = []
        client.last_processed_time = datetime.datetime.now()

        response = await chatgpt.get_ai_response(message)
        # print(response)
        for line in response.split('\n'):
            line = line.strip().strip('\n').strip()
            if line == "":
                continue
            try:
                print(line)
                async with msg.channel.typing():
                    exec_result = await execute_gpt_instruction(line, msg)
            except Exception as e:
                print(e)
                exec_result = False, f"Error executing instruction: {e}"

            if exec_result[0]:
                print(f'Executed instruction: {exec_result[1]}')
            else:
                print(f'Failed to execute instruction: {exec_result[1]}')

            if exec_result[1].split(" ")[0] not in ["Ignoring", "Replied", "Unknown"]:
                await msg.channel.send(exec_result[1])

load_dotenv()
client.run(os.getenv('TOKEN'))