import discord
from discord.ext import commands
from core import checks
from core.models import PermissionLevel

class PendingClose(commands.Cog):
    """Move thread to a pending close category when a timed close is initiated."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.pending_close_category_id = None
        self.bot.loop.create_task(self._load_config())

    async def _load_config(self):
        config = await self.db.find_one({"_id": "config"})
        if config:
            self.pending_close_category_id = config.get("pending_close_category_id")

    async def _save_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {"pending_close_category_id": self.pending_close_category_id}},
            upsert=True,
        )

    @commands.Cog.listener()
    async def on_thread_close(self, thread, closer, silent, delete_channel, message, scheduled):
        # Only move if this is a scheduled (timed) close
        if scheduled and self.pending_close_category_id:
            category = discord.utils.get(thread.channel.guild.categories, id=int(self.pending_close_category_id))
            if category and thread.channel.category_id != category.id:
                await thread.channel.edit(category=category, reason="Thread scheduled for close (pending close).")

    @commands.group(invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def pendingcloseconfig(self, ctx):
        """View the pending close category config."""
        cat = self.pending_close_category_id or "Not set"
        await ctx.send(f"Pending close category ID: `{cat}`")

    @pendingcloseconfig.command(name="set")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def set_category(self, ctx, category: discord.CategoryChannel):
        """Set the pending close category."""
        self.pending_close_category_id = category.id
        await self._save_config()
        await ctx.send(f"Pending close category set to: `{category.name}` (`{category.id}`)")

    @pendingcloseconfig.command(name="clear")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def clear_category(self, ctx):
        """Clear the pending close category."""
        self.pending_close_category_id = None
        await self._save_config()
        await ctx.send("Pending close category cleared.")

async def setup(bot):
    await bot.add_cog(PendingClose(bot))