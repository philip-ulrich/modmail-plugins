import re
import discord
from discord.ext import commands
from core import checks
from core.models import PermissionLevel


class Impersonation(commands.Cog):
    """Allows authorized roles to impersonate users in modmail threads."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.allowed_roles = []
        bot.loop.create_task(self._set_val())

    async def _update_db(self):
        """Save current config to database"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {
                'allowed_roles': self.allowed_roles
            }},
            upsert=True
        )

    async def _set_val(self):
        """Retrieve configuration from database"""
        config = await self.db.find_one({'_id': 'config'})
        
        if config is None:
            await self.db.find_one_and_update(
                {'_id': 'config'},
                {'$set': {
                    'allowed_roles': []
                }},
                upsert=True
            )
            return
        
        self.allowed_roles = config.get('allowed_roles', [])

    def _has_allowed_role(self, member):
        """Check if member has any allowed role"""
        return any(role.id in self.allowed_roles for role in member.roles)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Intercept messages to handle impersonation before normal command processing"""
        if not message.guild or message.author.bot:
            return
            
        # Check if this is in a modmail thread channel
        if not hasattr(self.bot, 'threads') or not self.bot.threads:
            return
            
        thread = None
        for t in self.bot.threads.cache:
            if t.channel and t.channel.id == message.channel.id:
                thread = t
                break
                
        if not thread:
            return
            
        # Check for reply command with impersonate pattern
        content = message.content.strip()
        
        # Handle different reply command variations
        reply_patterns = [
            rf'^{re.escape(self.bot.prefix)}r(?:eply)?\s+impersonate:(\d+)\s+(.*)',
            rf'^{re.escape(self.bot.prefix)}freply\s+impersonate:(\d+)\s+(.*)',
            rf'^{re.escape(self.bot.prefix)}areply\s+impersonate:(\d+)\s+(.*)',
            rf'^{re.escape(self.bot.prefix)}preply\s+impersonate:(\d+)\s+(.*)'
        ]
        
        for pattern in reply_patterns:
            match = re.match(pattern, content, re.DOTALL)
            if match:
                # Check if user has permission
                if not self._has_allowed_role(message.author):
                    await message.add_reaction('❌')
                    return
                    
                user_id, impersonate_message = match.groups()
                
                try:
                    # Get the user to impersonate
                    user_to_impersonate = await self.bot.fetch_user(int(user_id))
                    
                    # Create fake message object for impersonation
                    class FakeAuthor:
                        def __init__(self, user):
                            self.id = user.id
                            self.name = user.name
                            self.display_name = user.display_name
                            self.avatar = user.avatar
                            self.discriminator = getattr(user, 'discriminator', '0')
                            self.mention = user.mention
                            self.roles = []

                    class FakeMessage:
                        def __init__(self, content, author):
                            self.content = content
                            self.author = author
                            self.attachments = message.attachments
                            self.stickers = getattr(message, 'stickers', [])
                            self.created_at = message.created_at
                            self.id = message.id

                    fake_author = FakeAuthor(user_to_impersonate)
                    fake_message = FakeMessage(impersonate_message, fake_author)
                    
                    # Send the impersonated message directly through thread
                    await thread.send(fake_message, destination=thread.recipient, from_mod=False)
                    
                    # Delete the original command message
                    try:
                        await message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                        
                    # Prevent further command processing
                    return
                        
                except ValueError:
                    await message.add_reaction('❌')
                except discord.NotFound:
                    await message.add_reaction('❌')
                except Exception:
                    await message.add_reaction('❌')

    @commands.group(name="impersonateconfig", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def impersonateconfig(self, ctx):
        """Configure impersonation settings"""
        embed = discord.Embed(
            title="Impersonation Configuration",
            color=self.bot.main_color
        )
        
        allowed_roles = []
        for role_id in self.allowed_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                allowed_roles.append(f"{role.name} (`{role.id}`)")
        
        embed.add_field(
            name="Allowed Roles",
            value="\n".join(allowed_roles) if allowed_roles else "None",
            inline=False
        )
        
        embed.add_field(
            name="Usage",
            value="Use `?r impersonate:USER_ID message content` to impersonate a user",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @impersonateconfig.command(name="addrole")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def add_role(self, ctx, *, role: discord.Role):
        """Add a role to the allowed impersonation roles list"""
        if role.id in self.allowed_roles:
            await ctx.send("This role is already allowed to use impersonation.")
            return
            
        self.allowed_roles.append(role.id)
        await self._update_db()
        await ctx.send(f"Added {role.name} to allowed impersonation roles.")

    @impersonateconfig.command(name="removerole")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def remove_role(self, ctx, *, role: discord.Role):
        """Remove a role from the allowed impersonation roles list"""
        if role.id not in self.allowed_roles:
            await ctx.send("This role is not in the allowed list.")
            return
            
        self.allowed_roles.remove(role.id)
        await self._update_db()
        await ctx.send(f"Removed {role.name} from allowed impersonation roles.")


async def setup(bot):
    await bot.add_cog(Impersonation(bot))