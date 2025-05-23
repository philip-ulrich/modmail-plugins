import asyncio
import discord
from discord.ext import commands
from core import checks
from core.models import PermissionLevel

class PendingClose(commands.Cog):
    """Move thread to a pending close category when a timed close is initiated."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.pending_category = None
        self.additional_categories = []
        asyncio.create_task(self._set_val())

    async def _update_db(self):
        """Save current config to database"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {
                'pending_category': self.pending_category,
                'additional_categories': self.additional_categories
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
                    'pending_category': None,
                    'additional_categories': []
                }},
                upsert=True
            )
            return
        
        self.pending_category = config.get('pending_category')
        self.additional_categories = config.get('additional_categories', [])

    @commands.Cog.listener()
    async def on_message(self, message):
        """Move thread to pending category when ?close is used with a time"""
        if message.author.bot:
            return

        if not message.content.startswith(self.bot.prefix):
            return

        if "close" not in message.content.lower():
            return

        # Extract the time component if it exists
        if " in " not in message.content.lower():
            return

        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return

        if not self.pending_category:
            return

        # Check if the channel is in any of the valid categories
        channel_category = channel.category_id
        valid_categories = [self.pending_category] + self.additional_categories
        
        if channel_category not in valid_categories:
            return

        # Move the thread to pending category
        try:
            pending_category = discord.utils.get(channel.guild.categories, id=int(self.pending_category))
            if pending_category is None:
                await channel.send("Could not find the pending category. Please check the configuration.")
                return
            await channel.edit(category=pending_category)
        except discord.Forbidden:
            await channel.send("I don't have permission to move this channel.")
        except Exception as e:
            await channel.send(f"Error moving channel: {str(e)}")

    @commands.group(invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def pendingconfig(self, ctx):
        """Configure pending close category settings"""
        embed = discord.Embed(colour=self.bot.main_color)
        embed.set_author(name="Pending Close Category Configuration:", icon_url=self.bot.user.avatar.url)
        embed.add_field(name="Pending Category", value=f"`{self.pending_category}`", inline=False)
        embed.set_footer(text=f"To change category, use {self.bot.prefix}pendingconfig category <category ID>")
        await ctx.send(embed=embed)

    @pendingconfig.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def category(self, ctx, category_id: str = None):
        """Set the pending close category"""
        if category_id is None:
            embed = discord.Embed(
                title="Error",
                color=self.bot.error_color,
                description="Please provide a category ID.",
            )
            return await ctx.send(embed=embed)
            
        try:
            category = discord.utils.get(ctx.guild.categories, id=int(category_id))
            if not category:
                raise ValueError
        except (ValueError, TypeError):
            embed = discord.Embed(
                title="Error",
                description="Invalid category ID provided.",
                color=self.bot.error_color,
            )
            return await ctx.send(embed=embed)

        self.pending_category = str(category.id)
        await self._update_db()

        embed = discord.Embed(
            title="Success",
            color=self.bot.main_color,
            description=f"Pending category set to {category.name} (`{category.id}`)."
        )
        await ctx.send(embed=embed)

    @pendingconfig.command(name="add")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def add_category(self, ctx, *, category: int):
        """Add a category to check for timed close commands"""
        if category in self.additional_categories:
            await ctx.send("This category is already in the list.")
            return
            
        self.additional_categories.append(category)
        await self._update_db()
        await ctx.send(f"Added category {category} to the pending close check list.")

    @pendingconfig.command(name="remove")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def remove_category(self, ctx, *, category: int):
        """Remove a category from the check list"""
        if category not in self.additional_categories:
            await ctx.send("This category is not in the list.")
            return
            
        self.additional_categories.remove(category)
        await self._update_db()
        await ctx.send(f"Removed category {category} from the pending close check list.")

    @pendingconfig.command(name="list")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def list_categories(self, ctx):
        """List all categories being checked for timed close commands"""
        embed = discord.Embed(
            title="Pending Close Categories",
            color=self.bot.main_color
        )
        
        embed.add_field(
            name="Pending Category",
            value=f"{self.pending_category or 'Not Set'}"
        )
        
        additional = "\n".join(str(cat) for cat in self.additional_categories) or "None"
        embed.add_field(
            name="Additional Categories",
            value=additional,
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PendingClose(bot))