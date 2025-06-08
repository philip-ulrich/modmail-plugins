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
        """Listen for messages with impersonate command"""
        if not message.content.startswith('?impersonate'):
            return
            
        # Check if author has allowed role
        if not self._has_allowed_role(message.author):
            await message.add_reaction('❌')
            return
            
        # Parse the command manually
        parts = message.content.split(' ', 2)
        if len(parts) < 3:
            await message.add_reaction('❌')
            return
            
        try:
            # Get user from mention or ID
            user_str = parts[1]
            if user_str.startswith('<@') and user_str.endswith('>'):
                user_id = int(user_str[2:-1].replace('!', ''))
            else:
                user_id = int(user_str)
                
            user = self.bot.get_user(user_id)
            if not user:
                user = await self.bot.fetch_user(user_id)
                
            message_content = parts[2]
            
            # Create fake context for permission checking
            ctx = await self.bot.get_context(message)
            
            # Call the impersonate logic directly (skip role check since we already did it)
            await self._do_impersonate_direct(ctx, user, message_content)
            
        except (ValueError, IndexError, Exception) as e:
            await message.add_reaction('❌')

    # @commands.command(name="impersonate")
    # @checks.has_permissions(PermissionLevel.SUPPORTER)
    # @checks.thread_only()
    # async def impersonate(self, ctx, user: discord.User, *, message_content):
    #     """Impersonate a user in the current thread"""
    #     await self._do_impersonate(ctx, user, message_content)
        
    async def _do_impersonate(self, ctx, user: discord.User, message_content):
        """Impersonate a user in the current thread"""
        
        # Check if user has permission
        if not self._has_allowed_role(ctx.author):
            await ctx.message.add_reaction('❌')
            return
            
        await self._do_impersonate_direct(ctx, user, message_content)
        
    async def _do_impersonate_direct(self, ctx, user: discord.User, message_content):
        """Impersonate a user in the current thread (no permission check)"""
            
        try:
            # User is already provided by discord.py converter
            user_to_impersonate = user
            
            # Try to get member info from the guild to get roles
            member_to_impersonate = None
            try:
                member_to_impersonate = ctx.guild.get_member(user.id)
                if not member_to_impersonate:
                    member_to_impersonate = await ctx.guild.fetch_member(user.id)
            except:
                pass  # User might not be in the server
            
            # Delete the original command message
            try:
                await ctx.message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            
            # Create fake message object for impersonation
            class FakeAuthor:
                def __init__(self, user, member=None):
                    self.id = user.id
                    self.name = user.name
                    self.display_name = member.display_name if member else user.display_name
                    self.avatar = user.avatar
                    self.discriminator = getattr(user, 'discriminator', '0')
                    self.mention = user.mention
                    self.bot = False
                    self.system = False
                    
                    # Use member info if available for roles and guild info
                    if member:
                        self.roles = member.roles
                        self.guild = member.guild
                        self.top_role = member.top_role
                        self.color = member.color
                        self.colour = member.colour
                    else:
                        self.roles = []
                        self.guild = None
                        self.top_role = None
                        self.color = discord.Color.default()
                        self.colour = discord.Color.default()
                    
                def __str__(self):
                    return self.name
                    
                def __repr__(self):
                    return f"<FakeUser id={self.id} name='{self.name}'>"

            class FakeMessage:
                def __init__(self, content, author):
                    self.content = content
                    self.author = author
                    self.attachments = []
                    self.stickers = []
                    self.created_at = ctx.message.created_at
                    self.id = ctx.message.id
                    self.guild = ctx.message.guild
                    self.channel = ctx.message.channel
                    self.embeds = []
                    self.reactions = []
                    self.mention_everyone = False
                    self.mentions = []
                    self.role_mentions = []

            fake_author = FakeAuthor(user_to_impersonate, member_to_impersonate)
            fake_message = FakeMessage(message_content, fake_author)
            
            # Send the impersonated message directly through thread
            await ctx.thread.reply(fake_message)
                
        except ValueError:
            await ctx.message.add_reaction('❌')
        except discord.NotFound:
            await ctx.message.add_reaction('❌')
        except Exception as e:
            await ctx.message.add_reaction('❌')
            print(f"Impersonation error: {e}")  # For debugging

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
            value="Use `?impersonate @user message content` or `?impersonate USER_ID message content` to impersonate a user",
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