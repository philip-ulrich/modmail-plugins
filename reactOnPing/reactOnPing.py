import discord
from discord.ext import commands
from core import checks
from core.models import PermissionLevel


class ReactOnPing(commands.Cog):
    """Reacts with an emoji when someone gets pinged."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.reaction_emoji = None  # will be set from config
        self.excluded_roles = []  # list of role IDs to ignore
        bot.loop.create_task(self._set_val())

    async def _update_db(self):
        """Save current config to database"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {
                'reaction_emoji': self.reaction_emoji,
                'excluded_roles': self.excluded_roles
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
                    'reaction_emoji': None,
                    'excluded_roles': []
                }},
                upsert=True
            )
            return
        
        self.reaction_emoji = config.get('reaction_emoji', "🔔")
        self.excluded_roles = config.get('excluded_roles', [])

    @commands.Cog.listener()
    async def on_message(self, message):
        if len(message.mentions):
            # Don't react if no emoji is set or author has excluded role
            if not self.reaction_emoji:
                return
                
            if any(role.id in self.excluded_roles for role in message.author.roles):
                return
                
            await message.add_reaction(self.reaction_emoji)

    @commands.group(name="pingreact", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def pingreact(self, ctx):
        """Configure ping reaction settings"""
        embed = discord.Embed(
            title="Ping Reaction Configuration",
            color=self.bot.main_color
        )
        
        embed.add_field(
            name="Current Emoji",
            value=self.reaction_emoji,
            inline=False
        )
        
        excluded_roles = []
        for role_id in self.excluded_roles:
            role = ctx.guild.get_role(int(role_id))
            if role:
                excluded_roles.append(f"{role.name} (`{role.id}`)")
        
        embed.add_field(
            name="Excluded Roles",
            value="\n".join(excluded_roles) if excluded_roles else "None",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @pingreact.command(name="emoji")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def set_emoji(self, ctx, emoji: str):
        """Set the emoji to use for ping reactions"""
        self.reaction_emoji = emoji
        await self._update_db()
        await ctx.send(f"Ping reaction emoji set to {emoji}")

    @pingreact.command(name="addrole")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def add_excluded_role(self, ctx, *, role: discord.Role):
        """Add a role to the excluded roles list"""
        if str(role.id) in self.excluded_roles:
            await ctx.send("This role is already excluded.")
            return
            
        self.excluded_roles.append(str(role.id))
        await self._update_db()
        await ctx.send(f"Added {role.name} to excluded roles.")

    @pingreact.command(name="removerole")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def remove_excluded_role(self, ctx, *, role: discord.Role):
        """Remove a role from the excluded roles list"""
        if str(role.id) not in self.excluded_roles:
            await ctx.send("This role is not in the excluded list.")
            return
            
        self.excluded_roles.remove(str(role.id))
        await self._update_db()
        await ctx.send(f"Removed {role.name} from excluded roles.")
