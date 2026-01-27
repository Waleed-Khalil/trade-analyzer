"""
Trade Analyzer - Main Entry Point
Listens to Discord, parses trades, analyzes, and responds.
"""

import os
import sys
import asyncio
import discord
from discord.ext import commands
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.trade_parser import TradeParser, OptionTrade
from risk_engine.risk_engine import RiskEngine
from analysis.trade_analyzer import TradeAnalyzer
from discord_output.discord_output import DiscordOutput
import yaml


class TradeAnalyzerBot(commands.Bot):
    """
    Discord bot that monitors channels for trade alerts.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize components
        self.parser = TradeParser(config_path)
        self.engine = RiskEngine(config_path)
        self.analyzer = TradeAnalyzer(config_path)
        self.output = DiscordOutput(config_path)
        
        # Discord setup
        token = self.config.get('discord', {}).get('bot_token', os.getenv('DISCORD_BOT_TOKEN'))
        self.target_channel = self.config.get('discord', {}).get('channel_id', os.getenv('DISCORD_CHANNEL_ID'))
        
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
    
    async def on_ready(self):
        print(f"🤖 Trade Analyzer logged in as {self.user}")
        print(f"📡 Monitoring channel: {self.target_channel}")
    
    async def on_message(self, message):
        """
        Process incoming messages for trade alerts.
        Ignores messages from bots.
        """
        # Ignore bot messages (including own)
        if message.author.bot:
            return
        
        # Optionally: restrict to specific channel
        # if str(message.channel.id) != self.target_channel:
        #     return
        
        # Try to parse as trade alert
        trade = self.parser.parse(message.content)
        
        if trade:
            await self.process_trade(message.channel, trade, message.content)
        
        # Don't forget to process commands
        await self.process_commands(message)
    
    async def process_trade(self, channel, trade: OptionTrade, raw_message: str):
        """
        Process a parsed trade: analyze and respond.
        """
        print(f"\n{'='*60}")
        print(f"📨 Trade Detected: {trade.ticker} {trade.option_type} ${trade.strike}")
        print(f"   Premium: ${trade.premium}")
        print(f"{'='*60}")
        
        # Create trade plan
        # Note: Would need real-time price in production
        trade_plan = self.engine.create_trade_plan(trade)
        
        # AI analysis
        analysis = self.analyzer.analyze(trade, trade_plan)
        
        # Format and send response
        response = self.output.format_response(trade_plan, analysis)
        
        if 'content' in response:
            await channel.send(response['content'])
        elif 'embeds' in response:
            await channel.send(**response)
        
        # Log result
        print(f"\n✅ Decision: {trade_plan.go_no_go}")
        if trade_plan.go_no_go_reasons:
            for r in trade_plan.go_no_go_reasons:
                print(f"   → {r}")
        print(f"📊 Position: {trade_plan.position.contracts} contracts")
        print(f"🛡️ Stop: ${trade_plan.stop_loss} | 🎯 Target: ${trade_plan.target_1}")


async def main():
    """Main entry point"""
    # Check for token
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    
    bot = TradeAnalyzerBot(config_path)
    
    print("🚀 Trade Analyzer starting...")
    print("📝 Configuration loaded from:", config_path)
    
    async with bot:
        await bot.start(bot.config.get('discord', {}).get('bot_token'))


if __name__ == "__main__":
    asyncio.run(main())
