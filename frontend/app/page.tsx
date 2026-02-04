"use client"

import { useState } from "react"
import { analyzePlay, type AnalyzeResponse } from "@/lib/api"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-700/60 bg-slate-900/50 overflow-hidden">
      <h2 className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-700/60 bg-slate-800/30">
        {title}
      </h2>
      <div className="p-4 text-sm text-slate-300">{children}</div>
    </section>
  )
}

function ResultView({ data }: { data: AnalyzeResponse }) {
  const rec = data.recommendation.recommendation
  const isPlay = rec === "PLAY" || rec === "GO"
  const ctx = data.market_context as Record<string, unknown>
  const greeks = (ctx.greeks as Record<string, number>) ?? {}
  const stressTest = Array.isArray(ctx.stress_test) ? ctx.stress_test as Array<[number, number, number]> : []
  const theta1d = Array.isArray(ctx.theta_stress_1d) ? ctx.theta_stress_1d as Array<[string, number, number]> : []
  const scenarioProbs = Array.isArray(ctx.scenario_probs) ? ctx.scenario_probs as Array<[number, number]> : []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero verdict */}
      <div className={`rounded-2xl border-2 p-6 text-center ${isPlay ? "border-emerald-500/60 bg-emerald-500/10" : "border-amber-500/60 bg-amber-500/10"}`}>
        <p className="text-slate-400 text-sm uppercase tracking-wider mb-1">
          {data.trade.ticker} {data.trade.option_type} ${data.trade.strike}
        </p>
        <p className="text-4xl font-bold tracking-tight">
          <span className={isPlay ? "text-emerald-400" : "text-amber-400"}>{rec}</span>
        </p>
        <p className="text-slate-400 mt-2 text-sm">
          {data.trade_plan.position.contracts} contracts · Risk ${data.trade_plan.position.max_risk_dollars?.toFixed(0) ?? "—"} ({data.trade_plan.position.risk_percentage != null ? (data.trade_plan.position.risk_percentage * 100).toFixed(1) : "—"}%)
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Section title="Data used">
          <ul className="space-y-1.5">
            {data.current_price != null && (
              <li>Underlying: <span className="text-white font-mono">${data.current_price.toFixed(2)}</span></li>
            )}
            {data.option_live_price != null && (
              <li>Option (live): <span className="text-white font-mono">${data.option_live_price.toFixed(2)}</span></li>
            )}
            {ctx.break_even_price != null && (
              <li>Break-even: <span className="font-mono">${Number(ctx.break_even_price).toFixed(2)}</span></li>
            )}
            {ctx.moneyness_label != null && <li>{String(ctx.moneyness_label)}</li>}
            {ctx.market_status != null && typeof ctx.market_status === "object" && "market" in ctx.market_status && <li>Market: {String((ctx.market_status as { market?: string }).market)}</li>}
          </ul>
        </Section>

        <Section title="Greeks & probabilities">
          <ul className="space-y-1.5 font-mono text-slate-300">
            {greeks.delta != null && <li>Delta {greeks.delta.toFixed(2)}</li>}
            {greeks.theta != null && <li>Theta {greeks.theta.toFixed(4)}</li>}
            {ctx.implied_volatility != null && <li>IV {(Number(ctx.implied_volatility) * 100).toFixed(1)}%</li>}
            {ctx.probability_of_profit != null && <li>PoP {(Number(ctx.probability_of_profit) * 100).toFixed(0)}%</li>}
            {ctx.open_interest != null && <li>OI {Number(ctx.open_interest).toLocaleString()}</li>}
            {ctx.option_volume != null && <li>Vol {Number(ctx.option_volume).toLocaleString()}</li>}
          </ul>
        </Section>

        <Section title="Rule-based plan">
          <ul className="space-y-1.5">
            <li>Stop: <span className="font-mono text-amber-400">${data.trade_plan.stop_loss}</span></li>
            <li>T1: <span className="font-mono text-emerald-400">${data.trade_plan.target_1}</span> ({data.trade_plan.target_1_r}R)</li>
            <li>Runner: {data.trade_plan.runner_contracts} @ ${data.trade_plan.runner_target}</li>
            <li>Decision: <span className="font-semibold">{data.trade_plan.go_no_go}</span></li>
          </ul>
        </Section>
      </div>

      <Section title="Why">
        <div className="whitespace-pre-wrap text-slate-300">{data.recommendation.reasoning}</div>
      </Section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Risk assessment">
          <div className="whitespace-pre-wrap text-slate-300">{data.recommendation.risk_assessment}</div>
        </Section>
        <Section title="Entry & exit">
          <div className="space-y-3">
            <div><span className="text-slate-500 text-xs uppercase">Entry</span><div className="whitespace-pre-wrap text-slate-300 mt-0.5">{data.recommendation.entry_criteria}</div></div>
            <div><span className="text-slate-500 text-xs uppercase">Exit</span><div className="whitespace-pre-wrap text-slate-300 mt-0.5">{data.recommendation.exit_strategy}</div></div>
          </div>
        </Section>
      </div>

      {stressTest.length > 0 && (
        <Section title="Stress test (instant move)">
          <ul className="space-y-1 font-mono text-sm">
            {stressTest.map(([pct, pl], i) => (
              <li key={i}>
                {(pct * 100).toFixed(1)}%: <span className={pl >= 0 ? "text-emerald-400" : "text-red-400"}>{pl >= 0 ? "+" : ""}{pl?.toFixed(0)}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {theta1d.length > 0 && (
        <Section title="1-day hold estimates">
          <ul className="space-y-1 font-mono text-sm">
            {theta1d.map(([label, est], i) => (
              <li key={i}>{label}: ${est?.toFixed(2)}</li>
            ))}
          </ul>
        </Section>
      )}

      {scenarioProbs.length > 0 && (
        <Section title="Scenario probs (by exp)">
          <div className="flex flex-wrap gap-3 font-mono text-sm">
            {scenarioProbs.map(([pct, prob], i) => (
              <span key={i}>{(pct * 100) >= 0 ? "+" : ""}{(pct * 100).toFixed(0)}%: {(prob * 100).toFixed(0)}%</span>
            ))}
          </div>
        </Section>
      )}

      <Section title="Setup quality">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-semibold text-white">{data.analysis.setup_quality.toUpperCase()}</span>
          <span className="font-mono text-slate-400">Score: {data.analysis.setup_score}/100</span>
          <span className="text-slate-500">Confidence: {(data.analysis.confidence * 100).toFixed(0)}%</span>
          {data.analysis.score_breakdown && typeof data.analysis.score_breakdown === "object" && (
            <span className="text-xs text-slate-500 font-mono">
              {Object.entries(data.analysis.score_breakdown).map(([k, v]) => `${k}=${v}`).join(" ")}
            </span>
          )}
        </div>
      </Section>

      {data.analysis.red_flags.length > 0 && (
        <Section title="Red flags">
          <ul className="space-y-2">
            {data.analysis.red_flags.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-amber-200/90">
                <span className="text-amber-500 shrink-0">!</span>
                <span>{f.message}</span>
                {f.severity && <span className="text-slate-500 text-xs">[{f.severity}]</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {data.analysis.green_flags.length > 0 && (
        <Section title="Green flags">
          <ul className="space-y-1 text-emerald-200/90">
            {data.analysis.green_flags.map((f, i) => (
              <li key={i}>+ {f.message}</li>
            ))}
          </ul>
        </Section>
      )}

      {data.recommendation.support_resistance.length > 0 && (
        <Section title="Support & resistance">
          <ul className="space-y-1">
            {data.recommendation.support_resistance.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

export default function Home() {
  const [play, setPlay] = useState("")
  const [noAi, setNoAi] = useState(false)
  const [dte, setDte] = useState<string>("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setResult(null)
    const text = play.trim()
    if (!text) {
      setError("Paste an option play (e.g. MSFT 430 CALL @ 0.79 DTE 2)")
      return
    }
    setLoading(true)
    try {
      const data = await analyzePlay(text, {
        no_ai: noAi,
        dte_override: dte === "" ? null : parseInt(dte, 10),
      })
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen max-w-5xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-10">
        <h1 className="text-2xl font-bold text-white tracking-tight">Trade Analyzer</h1>
        <p className="text-slate-400 mt-1 text-sm">Paste an option play — get Go/No-Go, Greeks, risk, and recommendation.</p>
      </header>

      <form onSubmit={handleSubmit} className="mb-10">
        <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4 space-y-4">
          <label className="block">
            <span className="text-slate-400 text-sm block mb-1">Option play</span>
            <input
              type="text"
              value={play}
              onChange={(e) => setPlay(e.target.value)}
              placeholder="e.g. MSFT 430 CALL @ 0.79 EXP 2026-02-06"
              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 font-mono text-sm"
              disabled={loading}
            />
          </label>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-slate-400 text-sm cursor-pointer">
              <input type="checkbox" checked={noAi} onChange={(e) => setNoAi(e.target.checked)} className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500" />
              Rule-based only (no AI)
            </label>
            <label className="flex items-center gap-2 text-slate-400 text-sm">
              DTE override:
              <input
                type="number"
                min={0}
                value={dte}
                onChange={(e) => setDte(e.target.value)}
                placeholder="optional"
                className="w-20 px-2 py-1.5 rounded bg-slate-800 border border-slate-600 text-white text-sm font-mono"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm transition-colors"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-200 text-sm">
          {error}
        </div>
      )}

      {result && <ResultView data={result} />}
    </div>
  )
}
