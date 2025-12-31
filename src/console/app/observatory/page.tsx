"use client"

import { useEffect, useMemo, useState } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { AlertCircle } from "lucide-react"

type SeriesPoint = { timestamp: string; value: number }

type TokensPerSec = { prefill: number; decode: number }

type Panel<TSummary, TSeries> = {
  status: "online" | "warning" | "critical"
  summary: TSummary
  series: TSeries
}

type ObservatoryResponse = {
  quality: Panel<{ conflict_rate: number; unsupported_rate: number }, { conflict_rate: SeriesPoint[]; unsupported_rate: SeriesPoint[] }>
  context: Panel<{ tokens_per_claim: number; retrieval_hit_rate_at_5: number }, { tokens_per_claim: SeriesPoint[]; retrieval_hit_rate_at_5: SeriesPoint[] }>
  performance: Panel<{ p95_latency_ms: number; tokens_per_sec: TokensPerSec }, { p95_latency_ms: SeriesPoint[]; tokens_per_sec: { prefill: SeriesPoint[]; decode: SeriesPoint[] } }>
  hardware: Panel<{ uma_utilization_pct: number; kv_cache_fill_pct: number }, { uma_utilization_pct: SeriesPoint[]; kv_cache_fill_pct: SeriesPoint[] }>
  volume: Panel<{ minted_claims_24h: number }, { minted_claims_24h: SeriesPoint[] }>
}

type FetchState = {
  data?: ObservatoryResponse
  error?: string
  snapshotAgeSec: number
  lastUpdated?: number
}

const GOLD = "var(--gold-verified, #f3d27f)"
const BRAND = "var(--nvidia-green, #76b900)"
const PLATINUM = "var(--platinum-canonical, #94a3ff)"

function formatPct(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`
}

function formatLatency(value: number) {
  if (value >= 1000) return `${(value / 1000).toFixed(2)}s`
  return `${value.toFixed(0)}ms`
}

function Sparkline({
  data,
  color = BRAND,
  fillOpacity = 0.15,
  showAxis = false,
  gradientId,
}: {
  data: SeriesPoint[]
  color?: string
  fillOpacity?: number
  showAxis?: boolean
  gradientId: string
}) {
  const prepared = useMemo(() => data?.map((p) => ({ t: p.timestamp, v: p.value })) ?? [], [data])
  return (
    <ResponsiveContainer width="100%" height={80}>
      <AreaChart data={prepared}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={fillOpacity} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {showAxis ? <XAxis dataKey="t" hide /> : null}
        {showAxis ? <YAxis hide /> : null}
        <Tooltip
          contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}
          labelFormatter={(label) => new Date(label).toLocaleTimeString()}
          formatter={(value: number) => value.toFixed(3)}
        />
        <Area type="monotone" dataKey="v" stroke={color} fill={`url(#${gradientId})`} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function MiniLine({ data, color, gradientId }: { data: SeriesPoint[]; color: string; gradientId: string }) {
  const prepared = useMemo(() => data?.map((p) => ({ t: p.timestamp, v: p.value })) ?? [], [data])
  return (
    <ResponsiveContainer width="100%" height={120}>
      <LineChart data={prepared}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.4} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground) / 0.2)" vertical={false} />
        <XAxis dataKey="t" hide />
        <YAxis hide />
        <Tooltip
          contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}
          labelFormatter={(label) => new Date(label).toLocaleTimeString()}
          formatter={(value: number) => value.toFixed(2)}
        />
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={2.5} dot={false} />
        <Area type="monotone" dataKey="v" stroke="none" fill={`url(#${gradientId})`} />
      </LineChart>
    </ResponsiveContainer>
  )
}

function MiniBar({ data, color }: { data: SeriesPoint[]; color: string }) {
  const prepared = useMemo(() => data?.map((p, idx) => ({ idx, v: p.value })) ?? [], [data])
  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={prepared}>
        <XAxis dataKey="idx" hide />
        <YAxis hide />
        <Bar dataKey="v" fill={color} radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function GaugePill({ label, value, max = 100, dangerThreshold }: { label: string; value: number; max?: number; dangerThreshold?: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const isDanger = dangerThreshold !== undefined && value >= dangerThreshold
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border bg-card/70 p-4",
        isDanger ? "border-red-500/60 animate-pulse" : "border-border/60"
      )}
    >
      <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
        <span>{label}</span>
        <span>{value.toFixed(1)} / {max}</span>
      </div>
      <div className="w-full h-3 rounded-full bg-muted/40 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", isDanger ? "bg-red-500" : "bg-primary")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function LiveBadge({ age }: { age: number }) {
  const fresh = age <= 30
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={cn(
          "relative inline-flex h-3 w-3 rounded-full",
          fresh ? "bg-emerald-400" : "bg-amber-400",
          "after:absolute after:inset-[-4px] after:rounded-full after:border after:border-current after:animate-ping"
        )}
      />
      <span className="text-muted-foreground">{fresh ? "Live" : "Stale"} · {age.toFixed(0)}s</span>
    </div>
  )
}

export default function ObservatoryPage() {
  const [state, setState] = useState<FetchState>({ snapshotAgeSec: 0 })

  useEffect(() => {
    let active = true
    let timer: NodeJS.Timeout

    const fetchSnapshot = async () => {
      try {
        const res = await fetch("/api/system/observatory", { cache: "no-store" })
        if (!res.ok) {
          throw new Error(`Observatory unavailable: ${res.status}`)
        }
        const json = (await res.json()) as ObservatoryResponse
        const ageHeader = Number(res.headers.get("X-Vyasa-Snapshot-Age") || 0)
        if (!active) return
        setState({
          data: json,
          snapshotAgeSec: isFinite(ageHeader) ? ageHeader : 0,
          lastUpdated: Date.now(),
        })
      } catch (err: any) {
        if (!active) return
        setState((prev) => ({
          ...prev,
          error: err?.message || "Failed to load observatory",
        }))
      }
    }

    fetchSnapshot()
    timer = setInterval(fetchSnapshot, 10_000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const data = state.data
  const age = state.snapshotAgeSec ?? 0

  const qualitySeries = data?.quality.series ?? { conflict_rate: [], unsupported_rate: [] }
  const contextSeries = data?.context.series ?? { tokens_per_claim: [], retrieval_hit_rate_at_5: [] }
  const perfSeries = data?.performance.series ?? { p95_latency_ms: [], tokens_per_sec: { prefill: [], decode: [] } }
  const hardwareSeries = data?.hardware.series ?? { uma_utilization_pct: [], kv_cache_fill_pct: [] }
  const volumeSeries = data?.volume.series ?? { minted_claims_24h: [] }

  return (
    <div className="min-h-screen bg-background text-foreground px-4 md:px-8 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-wide text-muted-foreground">Vyasa Observatory</p>
          <h1 className="text-2xl md:text-3xl font-semibold">System Health & Gold Layer Pulse</h1>
        </div>
        <div className="flex items-center gap-3">
          {state.error ? (
            <div className="flex items-center gap-2 text-amber-400 text-sm">
              <AlertCircle className="h-4 w-4" />
              <span>{state.error}</span>
            </div>
          ) : (
            <LiveBadge age={age} />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {/* Quality */}
        <Card className="md:col-span-2 lg:col-span-2 bg-card/80 border-border/60">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Quality</CardTitle>
            <Badge variant="outline" className="border-amber-400/50 text-amber-200" style={{ color: GOLD, borderColor: GOLD }}>
              Vetted
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="relative h-24 w-24 rounded-full border-4 border-primary/40 flex items-center justify-center bg-muted/30">
                <div className="absolute inset-1 rounded-full border border-primary/30" />
                <span className="text-xl font-semibold text-primary">
                  {data ? formatPct(data.quality.summary.conflict_rate, 1) : "—"}
                </span>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Conflict Rate</p>
                <p className="text-lg font-medium">{data ? data.quality.summary.conflict_rate.toFixed(3) : "0.000"}</p>
                <p className="text-sm text-muted-foreground">Lower is better · Integrity gauge</p>
              </div>
            </div>
            <Separator />
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-muted-foreground">Unsupported Rate</p>
                <span className="text-sm font-medium">{data ? formatPct(data.quality.summary.unsupported_rate, 1) : "—"}</span>
              </div>
              <Sparkline data={qualitySeries.unsupported_rate} gradientId="spark-unsupported" color={PLATINUM} />
            </div>
          </CardContent>
        </Card>

        {/* Context */}
        <Card className="md:col-span-2 lg:col-span-2 bg-card/80 border-border/60">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Context</CardTitle>
            <Badge variant="secondary" className="text-xs">
              Hit Rate {data ? formatPct(data.context.summary.retrieval_hit_rate_at_5, 1) : "—"}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-muted-foreground">Tokens per Claim</p>
                <span className="text-sm font-semibold">{data ? data.context.summary.tokens_per_claim.toFixed(0) : "—"}</span>
              </div>
              <MiniLine data={contextSeries.tokens_per_claim} color={BRAND} gradientId="area-tpc" />
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-2 w-2 rounded-full bg-primary/70" />
              Retrieval Hit @5 trends
            </div>
            <Sparkline data={contextSeries.retrieval_hit_rate_at_5} gradientId="spark-hit" color={PLATINUM} />
          </CardContent>
        </Card>

        {/* Performance */}
        <Card className="md:col-span-2 lg:col-span-2 bg-card/80 border-border/60">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Performance</CardTitle>
            <Badge variant="outline" className="text-xs">p95 Latency</Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">p95 Latency</p>
                <p className="text-2xl font-semibold">{data ? formatLatency(data.performance.summary.p95_latency_ms) : "—"}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Prefill TPS</p>
                <p className="text-lg font-semibold text-primary">
                  {data ? data.performance.summary.tokens_per_sec.prefill.toFixed(1) : "—"}
                </p>
                <p className="text-sm text-muted-foreground">Decode TPS</p>
                <p className="text-lg font-semibold text-indigo-300">
                  {data ? data.performance.summary.tokens_per_sec.decode.toFixed(1) : "—"}
                </p>
              </div>
            </div>
            <MiniLine data={perfSeries.p95_latency_ms} color="var(--destructive, #ef4444)" gradientId="latency-line" />
          </CardContent>
        </Card>

        {/* Hardware */}
        <Card className="md:col-span-3 lg:col-span-3 bg-card/80 border-border/60">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Hardware</CardTitle>
            <Badge variant="outline" className="text-xs">128GB UMA · KV Cache</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <GaugePill
                label="VRAM / UMA"
                value={data?.hardware.summary.uma_utilization_pct ?? 0}
                max={128}
                dangerThreshold={90}
              />
              <GaugePill
                label="KV Cache Fill %"
                value={data?.hardware.summary.kv_cache_fill_pct ?? 0}
                max={100}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <p className="text-sm text-muted-foreground mb-1">UMA Utilization Trend</p>
                <Sparkline data={hardwareSeries.uma_utilization_pct} gradientId="spark-uma" color={BRAND} />
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">KV Cache Trend</p>
                <Sparkline data={hardwareSeries.kv_cache_fill_pct} gradientId="spark-kv" color={PLATINUM} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Volume */}
        <Card className="md:col-span-3 lg:col-span-3 bg-card/80 border-border/60">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Volume</CardTitle>
            <Badge variant="secondary" className="text-xs">24h</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Minted Claims (expert-verified)</p>
                <p className="text-4xl font-semibold text-primary">
                  {data ? data.volume.summary.minted_claims_24h.toLocaleString() : "—"}
                </p>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                Trend last 60 samples
              </div>
            </div>
            <MiniBar data={volumeSeries.minted_claims_24h} color={BRAND} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
