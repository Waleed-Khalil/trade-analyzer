const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export interface AnalyzeRequest {
  play: string
  no_ai?: boolean
  no_market?: boolean
  dte_override?: number | null
}

export interface AnalyzeResponse {
  ok: true
  trade: {
    ticker: string
    option_type: string
    strike: number
    premium: number
    expiration?: string
    days_to_expiration?: number
    is_ode?: boolean
  }
  trade_plan: {
    position: { contracts: number; max_risk_dollars: number; risk_percentage: number }
    stop_loss: number
    target_1: number
    target_1_r: number
    runner_contracts: number
    runner_target: number
    max_loss_dollars: number
    max_gain_dollars: number
    go_no_go: string
    go_no_go_reasons?: string[]
  }
  analysis: {
    summary: string
    red_flags: Array<{ type?: string; severity?: string; message: string }>
    green_flags: Array<{ type?: string; message: string }>
    setup_quality: string
    confidence: number
    setup_score: number
    score_breakdown?: Record<string, unknown>
  }
  recommendation: {
    recommendation: string
    reasoning: string
    risk_assessment: string
    entry_criteria: string
    exit_strategy: string
    market_context: string
    support_resistance: string[]
    ode_risks: string[]
  }
  market_context: Record<string, unknown>
  current_price: number | null
  option_live_price: number | null
}

export async function analyzePlay(play: string, options?: { no_ai?: boolean; no_market?: boolean; dte_override?: number | null }): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      play: play.trim(),
      no_ai: options?.no_ai ?? false,
      no_market: options?.no_market ?? false,
      dte_override: options?.dte_override ?? null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? res.statusText ?? "Analysis failed")
  }
  return res.json()
}
