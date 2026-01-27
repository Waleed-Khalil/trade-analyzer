"""
Discord Output Module
Format and send trade analysis to Discord
"""

from typing import Dict, Any
from datetime import datetime
import yaml
import os


class DiscordOutput:
    """
    Format and send trade analysis results to Discord.
    Supports compact and detailed output formats.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.discord_config = self.config.get('discord', {})
        self.template = self.discord_config.get('response_template', 'compact')
    
    def format_compact(self, trade_plan, analysis) -> Dict[str, Any]:
        """Compact format for quick scanning"""
        emoji = "✅" if trade_plan.go_no_go == "GO" else "❌"
        
        return {
            "content": (
                f"{emoji} **{trade_plan.trade.ticker}** {trade_plan.trade.option_type} ${trade_plan.trade.strike} "
                f"@ ${trade_plan.trade.premium:.2f}\n"
                f"**GO** | {trade_plan.position.contracts} contracts | "
                f"Stop ${trade_plan.stop_loss} | T1 ${trade_plan.target_1} ({trade_plan.target_1_r}R) | "
                f"Runner {trade_plan.runner_contracts} @ ${trade_plan.runner_target}"
            )
        }
    
    def format_detailed(self, trade_plan, analysis) -> Dict[str, Any]:
        """Detailed format with full analysis"""
        emoji = "✅" if trade_plan.go_no_go == "GO" else "❌"
        
        # Build field list
        fields = [
            {"name": "Decision", "value": f"{emoji} {trade_plan.go_no_go}", "inline": True},
            {"name": "Contracts", "value": str(trade_plan.position.contracts), "inline": True},
            {"name": "Risk", "value": f"${trade_plan.position.max_risk_dollars:.0f} ({trade_plan.position.risk_percentage:.1%})", "inline": True},
            {"name": "Entry Zone", "value": trade_plan.entry_zone, "inline": True},
            {"name": "Stop Loss", "value": f"${trade_plan.stop_loss} ({trade_plan.stop_risk_pct}%)", "inline": True},
            {"name": "Target 1", "value": f"${trade_plan.target_1} ({trade_plan.target_1_r}R)", "inline": True},
            {"name": "Runner", "value": f"{trade_plan.runner_contracts} contracts @ ${trade_plan.runner_target}", "inline": True},
            {"name": "Max Loss", "value": f"${trade_plan.max_loss_dollars:.2f}", "inline": True},
            {"name": "Max Gain", "value": f"${trade_plan.max_gain_dollars:.2f}", "inline": True},
        ]
        
        # Add analysis fields if available
        if analysis:
            fields.extend([
                {"name": "Setup Quality", "value": analysis.setup_quality.upper(), "inline": True},
                {"name": "Confidence", "value": f"{analysis.confidence:.0%}", "inline": True},
            ])
            
            if analysis.red_flags:
                flag_text = "\n".join([f"• {f['message']}" for f in analysis.red_flags])
                fields.append({"name": "⚠️ Red Flags", "value": flag_text, "inline": False})
        
        return {
            "embeds": [{
                "title": f"{trade_plan.trade.ticker} {trade_plan.trade.option_type} ${trade_plan.trade.strike}",
                "description": f"Premium: ${trade_plan.trade.premium:.2f}",
                "color": 0x00FF00 if trade_plan.go_no_go == "GO" else 0xFF0000,
                "fields": fields,
                "footer": {"text": f"Trade Analyzer • {datetime.utcnow().strftime('%H:%M:%S')}"}
            }]
        }
    
    def format_response(self, trade_plan, analysis) -> Dict[str, Any]:
        """Format response based on configured template"""
        if self.template == "compact":
            return self.format_compact(trade_plan, analysis)
        else:
            return self.format_detailed(trade_plan, analysis)
    
    async def send(self, channel_id: str, trade_plan, analysis):
        """
        Send formatted response to Discord channel.
        Would use discord.py or similar in production.
        """
        response = self.format_response(trade_plan, analysis)
        
        # In production:
        # channel = bot.get_channel(int(channel_id))
        # await channel.send(**response)
        
        print(f"[Discord] Would send to {channel_id}:")
        print(response)
        return response


# CLI test
if __name__ == "__main__":
    from parser.trade_parser import TradeParser
    from risk_engine import RiskEngine
    from analysis import TradeAnalyzer
    
    parser = TradeParser()
    engine = RiskEngine()
    analyzer = TradeAnalyzer()
    
    trade = parser.parse("BUY AAPL 01/31 215 CALL @ 3.50")
    if trade:
        plan = engine.create_trade_plan(trade, current_price=217.50)
        analysis = analyzer.analyze(trade, plan, current_price=217.50)
        
        print("="*60)
        print("COMPACT FORMAT")
        print("="*60)
        output = DiscordOutput()
        resp = output.format_compact(plan, analysis)
        print(resp['content'])
        
        print("\n" + "="*60)
        print("DETAILED FORMAT")
        print("="*60)
        output.template = "detailed"
        resp = output.format_detailed(plan, analysis)
        import json
        print(json.dumps(resp, indent=2))
