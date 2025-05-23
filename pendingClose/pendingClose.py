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
        self.category = None
        asyncio.create_task(self._set_val())

    async def _update_db(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {"category": self.category}},
            upsert=True,
        )

    async def _set_val(self):
        config = await self.db.find_one({"_id": "config"})
        if config:
            self.category = config.get("category", "")

    @commands.Cog.listener()
    async def on_thread_close(self, thread, closer, silent, delete_channel, message, scheduled):
        # Only move if this is a scheduled (timed) close
        if scheduled and self.category:
            category = discord.utils.get(thread.channel.guild.categories, id=int(self.category))
            if category and thread.channel.category_id != category.id:
                await thread.channel.edit(category=category, reason="Thread scheduled for close (pending close).")

    @commands.group(invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def pendingconfig(self, ctx):
        """Configure pending close category settings"""
        embed = discord.Embed(colour=self.bot.main_color)
        embed.set_author(name="Pending Close Category Configuration:", icon_url=self.bot.user.avatar.url)
        embed.add_field(name="Category", value=f"`{self.category}`", inline=False)
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

        self.category = str(category.id)
        await self._update_db()

        embed = discord.Embed(
            title="Success",
            color=self.bot.main_color,
            description=f"Category set to {category.name} (`{category.id}`)."
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PendingClose(bot))