#!/usr/bin/env python3
"""
Comprehensive Technical Analysis Module
Provides detailed technical analysis with explanations for traders.
"""

import sys
sys.path.insert(0, '/home/ubuntu/clawd/trade-analyzer/src')

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TechnicalLevels:
    """Key price levels"""
    current: float
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float
    sma_20: float
    sma_50: float
    sma_200: Optional[float]
    fib_382: float
    fib_500: float
    fib_618: float


@dataclass
class TechnicalIndicators:
    """Calculated technical indicators"""
    rsi: float
    rsi_signal: str  # oversold/neutral/overbought
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_signal_line: str  # bullish/bearish/neutral
    atr: float
    atr_percent: float
    volatility_rank: float  # 0-100
    volume_ratio: float
    volume_signal: str  # high/normal/low


@dataclass
class TrendAnalysis:
    """Trend analysis results"""
    short_term: str  # bullish/bearish/neutral
    medium_term: str
    long_term: str
    trend_strength: float  # 0-100
    moving_average_confluence: str
    price_vs_ma: str
    support_resessment: str


@dataclass  
class OptionAnalysis:
    """Options-specific analysis"""
    implied_volatility: float
    iv_rank: float
    iv_percentile: float
    historical_volatility: float
    iv_hv_ratio: float
    iv_signal: str  # low/favorable/elevated/dangerous
    theta: float
    theta_daily_decay: float
    gamma: float
    delta: float
    vega: float
    probability_of_profit: float
    pop_signal: str  # excellent/good/acceptable/poor/terrible
    days_to_expiration: int


@dataclass
class TradeSetup:
    """Complete trade setup analysis"""
    overall_score: int  # 0-100
    direction_preference: str  # bullish/bearish/neutral
    confidence: str  # high/medium/low
    setup_quality: str  # excellent/good/average/poor
    key_levels: TechnicalLevels
    indicators: TechnicalIndicators
    trend: TrendAnalysis
    options: OptionAnalysis
    pros: List[str]
    cons: List[str]
    recommendation: str
    risk_assessment: str


class TechnicalAnalyzer:
    """
    Comprehensive technical analysis for options trading.
    Provides detailed breakdowns with explanations.
    """
    
    def __init__(self, ticker: str, dte: int = 0):
        """
        Initialize analyzer.
        
        Args:
            ticker: Stock symbol (e.g., 'QQQ', 'AAPL')
            dte: Days to expiration (0 for 0DTE)
        """
        self.ticker = ticker.upper()
        self.dte = dte
        self.data = None
        self._fetch_data()
    
    def _fetch_data(self):
        """Fetch historical data"""
        if self.dte <= 1:
            # 0DTE or 1DTE: need more history for indicators
            periods = "3mo"
        elif self.dte <= 5:
            periods = "6mo"
        elif self.dte <= 21:
            periods = "1y"
        else:
            periods = "2y"
        
        self.stock = yf.Ticker(self.ticker)
        self.data = self.stock.history(period=periods)
        
        # Get options data if available
        self.options_data = None
        try:
            if self.stock.options:
                exp = self.stock.options[0]
                self.options_data = self.stock.option_chain(exp)
        except:
            pass
    
    def calculate_levels(self) -> TechnicalLevels:
        """
        Calculate key price levels.
        
        Explanation:
        - Pivot Point: Average of High, Low, Close (PP)
        - R1/R2/R3: Resistance levels above PP
        - S1/S2/S3: Support levels below PP
        - SMA: Simple Moving Averages for trend identification
        - Fibonacci: Retracements from recent high to low
        """
        high = self.data['High'].iloc[-1]
        low = self.data['Low'].iloc[-1]
        close = self.data['Close'].iloc[-1]
        current = close
        
        # Classic Pivot Points
        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        r2 = pp + (high - low)
        r3 = high + 2 * (pp - low)
        s1 = 2 * pp - high
        s2 = pp - (high - low)
        s3 = low - 2 * (high - pp)
        
        # Moving Averages
        sma_20 = self.data['Close'].rolling(20).mean().iloc[-1]
        sma_50 = self.data['Close'].rolling(50).mean().iloc[-1]
        sma_200 = None
        if len(self.data) >= 200:
            sma_200 = self.data['Close'].rolling(200).mean().iloc[-1]
        
        # Fibonacci Retracements (from recent swing high to low)
        lookback = min(30, len(self.data))
        period_high = self.data['High'].iloc[-lookback:].max()
        period_low = self.data['Low'].iloc[-lookback:].min()
        diff = period_high - period_low
        
        fib_382 = period_high - 0.382 * diff
        fib_500 = period_high - 0.5 * diff
        fib_618 = period_high - 0.618 * diff
        
        return TechnicalLevels(
            current=current,
            pivot=pp,
            r1=r1, r2=r2, r3=r3,
            s1=s1, s2=s2, s3=s3,
            sma_20=sma_20, sma_50=sma_50, sma_200=sma_200,
            fib_382=fib_382, fib_500=fib_500, fib_618=fib_618
        )
    
    def calculate_indicators(self) -> TechnicalIndicators:
        """
        Calculate and explain technical indicators.
        
        RSI (Relative Strength Index):
        - Measures overbought/oversold conditions
        - Above 70 = Overbought (potential reversal down)
        - Below 30 = Oversold (potential reversal up)
        - 50 = Neutral baseline
        
        MACD (Moving Average Convergence Divergence):
        - Trend-following momentum indicator
        - MACD > Signal = Bullish
        - MACD < Signal = Bearish
        - Histogram shows momentum acceleration
        
        ATR (Average True Range):
        - Measures volatility
        - Higher ATR = more volatile
        - ATR % shows volatility relative to price
        """
        close = self.data['Close']
        
        # RSI (14-period)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        
        if rsi_val > 70:
            rsi_signal = "overbought"
        elif rsi_val < 30:
            rsi_signal = "oversold"
        elif rsi_val > 50:
            rsi_signal = "neutral_bullish"
        else:
            rsi_signal = "neutral_bearish"
        
        # MACD (12, 26, 9)
        exp12 = close.ewm(span=12).mean()
        exp26 = close.ewm(span=26).mean()
        macd_line = exp12 - exp26
        macd_signal_line = macd_line.ewm(span=9).mean()
        macd_hist = macd_line - macd_signal_line
        
        macd_val = macd_line.iloc[-1]
        signal_val = macd_signal_line.iloc[-1]
        
        if macd_val > signal_val:
            macd_signal_line = "bullish"
        elif macd_val < signal_val:
            macd_signal_line = "bearish"
        else:
            macd_signal_line = "neutral"
        
        # ATR (14-period)
        high = self.data['High']
        low = self.data['Low']
        close_prev = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        atr_percent = (atr / close.iloc[-1]) * 100
        
        # Volume Analysis
        avg_volume = self.data['Volume'].rolling(20).mean().iloc[-1]
        current_volume = self.data['Volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume
        
        if volume_ratio > 1.5:
            volume_signal = "high"
        elif volume_ratio < 0.7:
            volume_signal = "low"
        else:
            volume_signal = "normal"
        
        # Volatility Rank (simplified)
        volatility_rank = min(100, (atr_percent / 3) * 50)  # Rough approximation
        
        return TechnicalIndicators(
            rsi=rsi_val,
            rsi_signal=rsi_signal,
            macd=macd_val,
            macd_signal=signal_val,
            macd_histogram=macd_hist.iloc[-1],
            macd_signal_line=macd_signal_line,
            atr=atr,
            atr_percent=atr_percent,
            volatility_rank=volatility_rank,
            volume_ratio=volume_ratio,
            volume_signal=volume_signal
        )
    
    def calculate_trend(self, levels: TechnicalLevels) -> TrendAnalysis:
        """
        Analyze trend direction and strength.
        
        Explanation:
        - Short-term: Price vs SMA 20
        - Medium-term: SMA 20 vs SMA 50
        - Long-term: SMA 50 vs SMA 200 (if available)
        - Golden Cross: 50 crosses above 200 = Bullish
        - Death Cross: 50 crosses below 200 = Bearish
        """
        current = levels.current
        price_vs_20 = "above" if current > levels.sma_20 else "below"
        price_vs_50 = "above" if current > levels.sma_50 else "below"
        
        # Short-term trend
        if current > levels.sma_20:
            short_term = "bullish"
        elif current < levels.sma_20:
            short_term = "bearish"
        else:
            short_term = "neutral"
        
        # Medium-term trend
        if levels.sma_20 > levels.sma_50:
            medium_term = "bullish"
        elif levels.sma_20 < levels.sma_50:
            medium_term = "bearish"
        else:
            medium_term = "neutral"
        
        # Long-term trend
        if levels.sma_200:
            if levels.sma_50 > levels.sma_200:
                long_term = "bullish"
            elif levels.sma_50 < levels.sma_200:
                long_term = "bearish"
            else:
                long_term = "neutral"
        else:
            long_term = "neutral"
        
        # Calculate trend strength (0-100)
        bullish_count = 0
        if current > levels.sma_20: bullish_count += 1
        if levels.sma_20 > levels.sma_50: bullish_count += 1
        if levels.sma_50 > levels.sma_200 if levels.sma_200 else False: bullish_count += 1
        trend_strength = (bullish_count / 3) * 100
        
        # Moving average confluence
        if abs(current - levels.sma_20) / current < 0.01:
            confluence = "price_at_ma"
        elif current > levels.sma_20 > levels.sma_50:
            confluence = "strong_bullish"
        elif current < levels.sma_20 < levels.sma_50:
            confluence = "strong_bearish"
        else:
            confluence = "mixed"
        
        # Support/Resistance assessment
        if current > levels.pivot:
            support_assessment = "testing_resistance"
        else:
            support_assessment = "seeking_support"
        
        return TrendAnalysis(
            short_term=short_term,
            medium_term=medium_term,
            long_term=long_term,
            trend_strength=trend_strength,
            moving_average_confluence=confluence,
            price_vs_ma=price_vs_20,
            support_resessment=support_assessment
        )
    
    def calculate_options_analysis(self, strike: float = None, 
                                   option_type: str = "CALL",
                                   premium: float = None) -> Optional[OptionAnalysis]:
        """
        Calculate options-specific metrics.
        
        Explanation:
        - Implied Volatility (IV): Market's expectation of future volatility
        - IV Rank: Current IV vs 52-week range (0-100)
        - IV > HV: Options expensive (IV crush risk)
        - IV < HV: Options cheap (favorable for buyers)
        - Theta: Daily time decay (negative = losing value)
        - Delta: Option's sensitivity to stock movement
        - Gamma: Delta's rate of change (acceleration)
        - Vega: Sensitivity to IV changes
        """
        if not self.options_data:
            # Estimate from available data
            close = self.data['Close'].iloc[-1]
            
            # Approximate IV from historical volatility
            returns = self.data['Close'].pct_change().dropna()
            hv = returns.std() * np.sqrt(252)  # Annualized
            
            iv = hv * 1.1  # Rough IV estimate
            
            return OptionAnalysis(
                implied_volatility=iv * 100,
                iv_rank=50,  # Unknown
                iv_percentile=50,
                historical_volatility=hv * 100,
                iv_hv_ratio=1.1,
                iv_signal="unknown",
                theta=0,
                theta_daily_decay=0,
                gamma=0,
                delta=0,
                vega=0,
                probability_of_profit=50,
                pop_signal="unknown",
                days_to_expiration=self.dte
            )
        
        # Get IV from options data
        current_iv = 0
        if option_type.upper() == "CALL":
            options = self.options_data.calls
        else:
            options = self.options_data.puts
        
        if strike and len(options) > 0:
            # Find closest strike
            options['strike_diff'] = abs(options['strike'] - strike)
            nearest = options.loc[options['strike_diff'].idxmin()]
            current_iv = nearest.get('impliedVolatility', 30) or 30
        else:
            current_iv = 30  # Default
        
        # Calculate approximate IV rank (simplified)
        # Real implementation would use 52-week option IV data
        hv = self.data['Close'].pct_change().dropna().std() * np.sqrt(252) * 100
        
        iv_rank = min(100, max(0, (current_iv - hv * 0.8) / (hv * 0.4) * 100))
        
        # IV Signal
        if current_iv < hv * 0.8:
            iv_signal = "low"
        elif current_iv < hv * 1.1:
            iv_signal = "favorable"
        elif current_iv < hv * 1.3:
            iv_signal = "elevated"
        else:
            iv_signal = "dangerous"
        
        # Estimate Greeks (simplified)
        if strike and len(options) > 0:
            delta = nearest.get('delta', 0.5) or 0.5
            gamma = nearest.get('gamma', 0.05) or 0.05
            theta = nearest.get('theta', -0.1) or -0.1
            vega = nearest.get('vega', 0.1) or 0.1
        else:
            # Rough estimates
            distance_pct = abs(strike - self.data['Close'].iloc[-1]) / self.data['Close'].iloc[-1]
            delta = 0.5 - distance_pct * 3  # Rough approximation
            gamma = 0.05
            theta = -premium / self.dte if self.dte > 0 else -premium / 1
            vega = 0.1
        
        # Theta daily decay (approximate)
        theta_daily_decay = abs(theta)
        
        # Probability of Profit (simplified - based on distance and IV)
        if strike:
            distance = abs(self.data['Close'].iloc[-1] - strike) / self.data['Close'].iloc[-1]
            # Higher IV = wider distribution = higher PoP for same distance
            pop = 50 - (distance * 1000) + (current_iv / 10)
            pop = max(5, min(95, pop))
        else:
            pop = 50
        
        # PoP Signal
        if pop >= 70:
            pop_signal = "excellent"
        elif pop >= 55:
            pop_signal = "good"
        elif pop >= 45:
            pop_signal = "acceptable"
        elif pop >= 30:
            pop_signal = "poor"
        else:
            pop_signal = "terrible"
        
        return OptionAnalysis(
            implied_volatility=current_iv * 100 if current_iv < 1 else current_iv,
            iv_rank=iv_rank,
            iv_percentile=50,
            historical_volatility=hv,
            iv_hv_ratio=current_iv / hv if hv > 0 else 1,
            iv_signal=iv_signal,
            theta=theta,
            theta_daily_decay=theta_daily_decay,
            gamma=gamma,
            delta=delta,
            vega=vega,
            probability_of_profit=pop,
            pop_signal=pop_signal,
            days_to_expiration=self.dte
        )
    
    def analyze(self, strike: float = None, option_type: str = "CALL",
                premium: float = None) -> TradeSetup:
        """
        Run complete technical analysis.
        
        Returns comprehensive analysis with scores and recommendations.
        """
        # Calculate all components
        levels = self.calculate_levels()
        indicators = self.calculate_indicators()
        trend = self.calculate_trend(levels)
        options = self.calculate_options_analysis(strike, option_type, premium)
        
        # Calculate overall score (0-100)
        score = 50  # Start neutral
        
        # Adjust for trend
        if trend.trend_strength > 70:
            score += 10
        elif trend.trend_strength < 30:
            score -= 10
        
        # Adjust for RSI
        if indicators.rsi_signal == "oversold":
            score += 5  # Oversold = potential bounce
        elif indicators.rsi_signal == "overbought":
            score -= 5  # Overbought = potential drop
        
        # Adjust for MACD
        if indicators.macd_signal_line == "bullish":
            score += 5
        elif indicators.macd_signal_line == "bearish":
            score -= 5
        
        # Adjust for IV
        if options:
            if options.iv_signal == "favorable":
                score += 10
            elif options.iv_signal == "dangerous":
                score -= 10
            
            if options.pop_signal == "excellent":
                score += 10
            elif options.pop_signal == "terrible":
                score -= 10
        
        score = max(0, min(100, score))
        
        # Determine direction preference
        if score >= 60:
            direction = "bullish"
        elif score <= 40:
            direction = "bearish"
        else:
            direction = "neutral"
        
        # Setup quality
        if score >= 80:
            quality = "excellent"
        elif score >= 65:
            quality = "good"
        elif score >= 45:
            quality = "average"
        else:
            quality = "poor"
        
        # Confidence
        if abs(score - 50) >= 30:
            confidence = "high"
        elif abs(score - 50) >= 15:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Generate pros and cons
        pros = []
        cons = []
        
        # Trend pros/cons
        if trend.short_term == "bullish":
            pros.append("Short-term trend is bullish")
        else:
            cons.append("Short-term trend is bearish")
        
        if trend.medium_term == "bullish":
            pros.append("Medium-term trend is bullish")
        else:
            cons.append("Medium-term trend is bearish")
        
        # RSI pros/cons
        if indicators.rsi_signal == "oversold":
            pros.append("RSI indicates oversold conditions (potential bounce)")
        elif indicators.rsi_signal == "overbought":
            cons.append("RSI indicates overbought conditions (reversal risk)")
        
        # MACD pros/cons
        if indicators.macd_signal_line == "bullish":
            pros.append("MACD is bullish (above signal line)")
        elif indicators.macd_signal_line == "bearish":
            cons.append("MACD is bearish (below signal line)")
        
        # IV pros/cons
        if options:
            if options.iv_signal == "favorable":
                pros.append("IV is favorable for options buyers")
            elif options.iv_signal == "dangerous":
                cons.append("IV is elevated (IV crush risk)")
            
            if options.probability_of_profit >= 50:
                pros.append(f"Probability of Profit: {options.probability_of_profit:.0f}%")
            else:
                cons.append(f"Low Probability of Profit: {options.probability_of_profit:.0f}%")
            
            if abs(options.theta_daily_decay) > 0.1 * premium if premium else False:
                cons.append(f"High theta decay (losing ${options.theta_daily_decay:.2f}/day)")
        
        # Risk assessment
        if score >= 70 and options and options.probability_of_profit >= 50:
            risk = "low"
        elif score >= 50 or (options and options.probability_of_profit >= 40):
            risk = "moderate"
        else:
            risk = "high"
        
        # Final recommendation
        if score >= 70 and direction == "bullish":
            recommendation = "FAVORABLE for CALLS"
        elif score <= 30 and direction == "bearish":
            recommendation = "FAVORABLE for PUTS"
        elif score >= 55:
            recommendation = "CAUTION - Slight bullish bias"
        elif score <= 45:
            recommendation = "CAUTION - Slight bearish bias"
        else:
            recommendation = "AVOID - No clear edge"
        
        return TradeSetup(
            overall_score=score,
            direction_preference=direction,
            confidence=confidence,
            setup_quality=quality,
            key_levels=levels,
            indicators=indicators,
            trend=trend,
            options=options,
            pros=pros,
            cons=cons,
            recommendation=recommendation,
            risk_assessment=risk
        )
    
    def print_detailed_report(self, setup: TradeSetup, strike: float = None,
                               option_type: str = "CALL", premium: float = None):
        """Print comprehensive technical analysis report."""
        
        l = setup.key_levels
        i = setup.indicators
        t = setup.trend
        o = setup.options
        
        print("=" * 80)
        print(f"COMPREHENSIVE TECHNICAL ANALYSIS: {self.ticker}")
        print("=" * 80)
        print()
        
        # PRICE ACTION
        print("-" * 80)
        print("PRICE ACTION")
        print("-" * 80)
        print(f"Current Price:     ${l.current:.2f}")
        print(f"Day Range:        ${self.data['Low'].iloc[-1]:.2f} - ${self.data['High'].iloc[-1]:.2f}")
        print(f"52w High:         ${self.data['High'].max():.2f}")
        print(f"52w Low:          ${self.data['Low'].min():.2f}")
        print()
        
        # KEY LEVELS
        print("-" * 80)
        print("KEY LEVELS (Pivot Point Analysis)")
        print("-" * 80)
        print(f"Resistance 3:     ${l.r3:.2f}")
        print(f"Resistance 2:     ${l.r2:.2f}")
        print(f"Resistance 1:     ${l.r1:.2f}")
        print("-" * 40)
        print(f"Pivot Point:      ${l.pivot:.2f}")
        print("-" * 40)
        print(f"Support 1:        ${l.s1:.2f}")
        print(f"Support 2:        ${l.s2:.2f}")
        print(f"Support 3:        ${l.s3:.2f}")
        print()
        
        # Moving Averages
        print("-" * 80)
        print("MOVING AVERAGES")
        print("-" * 80)
        print(f"SMA 20:           ${l.sma_20:.2f}  ({t.price_vs_ma} SMA 20)")
        print(f"SMA 50:           ${l.sma_50:.2f}")
        if l.sma_200:
            print(f"SMA 200:          ${l.sma_200:.2f}")
        print()
        
        # Fibonacci
        print("-" * 80)
        print("FIBONACCI RETRACEMENTS")
        print("-" * 80)
        print(f"0% (High):        ${l.fib_382:.2f}")
        print(f"38.2%:            ${l.fib_382:.2f}")
        print(f"50%:              ${l.fib_500:.2f}")
        print(f"61.8%:            ${l.fib_618:.2f}")
        print(f"100% (Low):       ${l.s3:.2f}")
        print()
        
        # TECHNICAL INDICATORS
        print("-" * 80)
        print("TECHNICAL INDICATORS")
        print("-" * 80)
        
        print(f"RSI (14):         {i.rsi:.1f}  [{i.rsi_signal}]")
        print("  → RSI Interpretation:")
        if i.rsi > 70:
            print("     Overbought. Price may reverse lower.")
        elif i.rsi < 30:
            print("     Oversold. Price may reverse higher.")
        elif i.rsi > 50:
            print("     Bullish bias. Momentum favoring buyers.")
        else:
            print("     Bearish bias. Momentum favoring sellers.")
        print()
        
        print(f"MACD:             {i.macd:.3f}")
        print(f"Signal Line:      {i.macd_signal:.3f}")
        print(f"Histogram:        {i.macd_histogram:.3f}  [{i.macd_signal_line}]")
        print("  → MACD Interpretation:")
        if i.macd_signal_line == "bullish":
            print("     Bullish momentum. MACD above signal line.")
        elif i.macd_signal_line == "bearish":
            print("     Bearish momentum. MACD below signal line.")
        else:
            print("     No clear momentum direction.")
        print()
        
        print(f"ATR (14):         ${i.atr:.2f} ({i.atr_percent:.1f}% of price)")
        print(f"Volatility Rank:  {i.volatility_rank:.0f}/100")
        print()
        
        print(f"Volume Ratio:     {i.volume_ratio:.1f}x average  [{i.volume_signal}]")
        print()
        
        # TREND ANALYSIS
        print("-" * 80)
        print("TREND ANALYSIS")
        print("-" * 80)
        print(f"Short-term:       {t.short_term.upper()}")
        print(f"Medium-term:      {t.medium_term.upper()}")
        print(f"Long-term:        {t.long_term.upper()}")
        print(f"Trend Strength:   {t.trend_strength:.0f}/100")
        print(f"MA Confluence:    {t.moving_average_confluence}")
        print()
        
        # OPTIONS ANALYSIS
        if o:
            print("-" * 80)
            print("OPTIONS ANALYSIS")
            print("-" * 80)
            print(f"Implied Vol:      {o.implied_volatility:.1f}%")
            print(f"IV Rank:          {o.iv_rank:.0f}/100")
            print(f"Historical Vol:    {o.historical_volatility:.1f}%")
            print(f"IV/HV Ratio:      {o.iv_hv_ratio:.2f}  [{o.iv_signal}]")
            print()
            print("→ IV Interpretation:")
            if o.iv_signal == "low":
                print("   Low IV. Options are cheap. Favorable for buyers.")
            elif o.iv_signal == "favorable":
                print("   Normal IV. Fair pricing for options.")
            elif o.iv_signal == "elevated":
                print("   Elevated IV. Options expensive. Beware IV crush.")
            else:
                print("   High IV. Very expensive options. Not favorable.")
            print()
            
            print("Greeks:")
            print(f"  Delta:         {o.delta:.4f}  (Stock move → Option move)")
            print(f"  Gamma:         {o.gamma:.4f}  (Delta's rate of change)")
            print(f"  Theta:         {o.theta:.4f}  (Daily time decay)")
            print(f"  Vega:          {o.vega:.4f}  (Sensitivity to IV)")
            print()
            
            print(f"Probability of Profit: {o.probability_of_profit:.0f}%  [{o.pop_signal}]")
            print()
            
            if o.days_to_expiration <= 1:
                print("⚠️ 0DTE/1DTE WARNING: Time decay accelerates!")
                print(f"   Theta decay: ~${o.theta_daily_decay:.2f}/day")
                print()
        
        # SUMMARY
        print("=" * 80)
        print("SUMMARY & RECOMMENDATION")
        print("=" * 80)
        print()
        print(f"OVERALL SCORE:     {setup.overall_score}/100  [{setup.setup_quality.upper()}]")
        print(f"DIRECTION:         {setup.direction_preference.upper()}")
        print(f"CONFIDENCE:        {setup.confidence.upper()}")
        print(f"RISK LEVEL:        {setup.risk_assessment.upper()}")
        print()
        print(f"RECOMMENDATION:    {setup.recommendation}")
        print()
        
        if setup.pros:
            print("PROS:")
            for p in setup.pros:
                print(f"  + {p}")
            print()
        
        if setup.cons:
            print("CONS:")
            for c in setup.cons:
                print(f"  - {c}")
            print()
        
        print("=" * 80)


# Helper function to run analysis
def run_full_analysis(ticker: str, strike: float = None, 
                      option_type: str = "CALL", premium: float = None,
                      dte: int = 0):
    """Run complete technical analysis on a ticker."""
    
    analyzer = TechnicalAnalyzer(ticker, dte)
    setup = analyzer.analyze(strike, option_type, premium)
    analyzer.print_detailed_report(setup, strike, option_type, premium)
    
    return setup


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Technical Analysis')
    parser.add_argument('ticker', help='Stock ticker')
    parser.add_argument('--strike', type=float, help='Option strike price')
    parser.add_argument('--type', default='CALL', help='Option type (CALL/PUT)')
    parser.add_argument('--premium', type=float, help='Option premium')
    parser.add_argument('--dte', type=int, default=0, help='Days to expiration')
    
    args = parser.parse_args()
    
    run_full_analysis(args.ticker, args.strike, args.type, args.premium, args.dte)
