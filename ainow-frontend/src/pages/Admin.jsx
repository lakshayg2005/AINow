import { useCallback, useEffect, useRef, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { useAuth } from "../context/auth"
import {
  deleteDraft,
  getAdminIssues,
  getAdminOverview,
  publishIssue,
  recheckIssue,
  retryFailedDeliveries,
  sendTestEmail,
  startComposeJob,
  startIngestJob,
} from "../services/api"

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

const STATUS_STYLES = {
  queued: "bg-neutral-700/40 text-neutral-300",
  running: "bg-sky-500/15 text-sky-300",
  completed: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-rose-500/15 text-rose-300",
  draft: "bg-amber-500/15 text-amber-300",
  published: "bg-emerald-500/15 text-emerald-300",
}

function Pill({ status }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLES[status] || STATUS_STYLES.queued}`}>
      {status === "running" && <span className="mr-1.5 mt-[5px] h-1.5 w-1.5 animate-pulse rounded-full bg-sky-300" />}
      {status}
    </span>
  )
}

// API timestamps are naive UTC.
function parseUtc(value) {
  if (!value) return null
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

function timeAgo(value) {
  const date = parseUtc(value)
  if (!date) return "never"

  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return "just now"
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`
  return `${Math.round(seconds / 86400)} d ago`
}

function duration(job) {
  const start = parseUtc(job.started_at)
  if (!start) return "—"
  const end = parseUtc(job.finished_at) || new Date()
  const seconds = Math.round((end - start) / 1000)
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function jobSummary(job) {
  if (job.status === "failed") return job.error || "Failed"
  const result = job.result || {}

  if (job.kind === "ingest" && result.ingest) {
    return `${result.ingest.new ?? 0} new items · ${result.stories?.new_stories ?? 0} new stories`
  }
  if (job.kind === "compose" && result.issue_id) {
    return `Draft #${result.issue_id}: ${result.headline || ""}`
  }
  if (job.kind === "deliver" && result.total !== undefined) {
    return `${result.sent} sent · ${result.failed} failed · ${result.skipped} skipped`
  }
  return ""
}

const SECTION_LABELS = {
  headline: "Headline",
  intro: "Intro",
  quick_news: "Quick News",
  research_spotlight: "Research",
  paper_of_week: "Paper of the Week",
  deep_dive: "Deep Dive",
  trends: "Trends",
  concept: "Concept",
  resources: "Resources",
  our_take: "Our Take",
  images: "Images",
  accuracy: "Accuracy",
  general: "General",
}

function reviewFixes(review) {
  if (!review) return 0
  return [...review.notes, ...review.checks].filter((note) => note.severity === "fix").length
}

function ScoreBadge({ review }) {
  if (!review) return null

  if (review.score == null) {
    return <span className="rounded-full bg-neutral-700/40 px-2.5 py-0.5 text-xs font-semibold text-neutral-300">Checks only</span>
  }

  const tone =
    review.score >= 8
      ? "bg-emerald-500/15 text-emerald-300"
      : review.score >= 6
        ? "bg-amber-500/15 text-amber-300"
        : "bg-rose-500/15 text-rose-300"

  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>Review {review.score}/10</span>
}

function ReviewNotes({ title, notes }) {
  if (notes.length === 0) return null

  // Fixes first.
  const ordered = [...notes].sort((a, b) => (a.severity === "fix" ? 0 : 1) - (b.severity === "fix" ? 0 : 1))

  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">{title}</p>
      <ul className="mt-2 flex flex-col gap-2">
        {ordered.map((note, index) => (
          <li key={index} className="flex gap-3 text-sm">
            <span
              className={`mt-0.5 h-fit shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                note.severity === "fix" ? "bg-rose-500/15 text-rose-300" : "bg-neutral-700/50 text-neutral-400"
              }`}
            >
              {note.severity}
            </span>
            <span className="text-neutral-300">
              <span className="font-semibold text-neutral-100">{SECTION_LABELS[note.section] || note.section}</span>
              {note.item && <span className="text-neutral-500"> · {note.item}</span>}
              <span className="block text-neutral-400">{note.note}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ReviewPanel({ review }) {
  if (!review) return null

  const fixes = reviewFixes(review)
  const total = review.notes.length + review.checks.length

  return (
    <details className="group mt-3 rounded-xl border border-neutral-800 bg-black/40">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-sm text-neutral-400 hover:text-neutral-200">
        <span className="transition group-open:rotate-90">›</span>
        {total === 0 ? "Review found nothing to change" : `${total} review note${total === 1 ? "" : "s"}`}
        {fixes > 0 && <span className="text-rose-300">· {fixes} to fix</span>}
        {review.verdict && <span className="hidden truncate text-neutral-500 md:inline">· {review.verdict}</span>}
      </summary>
      <div className="flex flex-col gap-5 border-t border-neutral-800 px-4 py-4">
        {review.verdict && <p className="text-sm text-neutral-300">{review.verdict}</p>}
        <ReviewNotes title="Editor's notes" notes={review.notes} />
        <ReviewNotes title="Automatic checks" notes={review.checks} />
        <p className="text-xs text-neutral-600">
          {review.model ? `Reviewed by ${review.model}` : "No model review"}
          {review.reviewed_at && ` · ${timeAgo(review.reviewed_at)}`}
        </p>
      </div>
    </details>
  )
}

function StatCard({ label, value, detail }) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-6">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-white">{value}</p>
      {detail && <p className="mt-2 text-sm text-neutral-500">{detail}</p>}
    </div>
  )
}

function Admin() {
  const { user, loading: authLoading } = useAuth()

  const [overview, setOverview] = useState(null)
  const [issues, setIssues] = useState([])
  const [error, setError] = useState("")
  const [toast, setToast] = useState(null)
  const [busy, setBusy] = useState({})
  const [confirming, setConfirming] = useState(null)
  const toastTimer = useRef(null)

  const load = useCallback(async () => {
    try {
      const [overviewData, issueData] = await Promise.all([getAdminOverview(), getAdminIssues()])
      setOverview(overviewData)
      setIssues(issueData)
      setError("")
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    if (!user?.is_admin) return undefined

    let cancelled = false

    Promise.all([getAdminOverview(), getAdminIssues()])
      .then(([overviewData, issueData]) => {
        if (cancelled) return
        setOverview(overviewData)
        setIssues(issueData)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [user])

  // Poll while any job is queued or running.
  const hasActiveJob = overview?.jobs?.some((job) => ["queued", "running"].includes(job.status))

  useEffect(() => {
    if (!hasActiveJob) return undefined
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [hasActiveJob, load])

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  function notify(message, kind = "ok") {
    setToast({ message, kind })
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 5000)
  }

  async function run(key, action, successMessage) {
    setBusy((current) => ({ ...current, [key]: true }))
    try {
      const result = await action()
      notify(typeof successMessage === "function" ? successMessage(result) : successMessage)
      await load()
    } catch (err) {
      notify(err.message, "error")
    } finally {
      setBusy((current) => ({ ...current, [key]: false }))
    }
  }

  if (authLoading) {
    return <main className="min-h-screen bg-black p-24 text-neutral-400">Loading…</main>
  }

  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />
  }

  const activeKinds = new Set(
    (overview?.jobs || []).filter((job) => ["queued", "running"].includes(job.status)).map((job) => job.kind)
  )
  const lastIngest = overview?.last_ingest
  const scheduler = overview?.scheduler

  return (
    <main className="min-h-screen bg-black px-6 py-16 text-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-12">
        <header className="flex flex-col gap-2">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-400">Admin</p>
          <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Newsroom</h1>
          <p className="text-neutral-400">Fetch the news, generate a draft, review it, then publish to subscribers.</p>
        </header>

        {error && <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-300">{error}</p>}

        {/* ---------------------------------------------- Stats */}
        {overview && (
          <section className="grid gap-4 md:grid-cols-4">
            <StatCard label="Active subscribers" value={overview.subscribers} detail="Verified, receiving email" />
            <StatCard label="Stories this week" value={overview.stories_this_week} detail="Clustered from all sources" />
            <StatCard
              label="Last news fetch"
              value={lastIngest ? timeAgo(lastIngest.started_at) : "never"}
              detail={lastIngest ? `${lastIngest.totals?.kept ?? 0} items · ${lastIngest.totals?.new ?? 0} new` : "Run it below"}
            />
            <StatCard
              label="Scheduler"
              value={scheduler?.enabled ? "On" : "Off"}
              detail={
                scheduler?.enabled
                  ? `Fetch every ${scheduler.ingest_every_hours}h · draft ${WEEKDAYS[scheduler.compose_weekday]} ${scheduler.compose_hour_utc}:00 UTC${scheduler.auto_publish ? " · auto-publish" : ""}`
                  : "Set SCHEDULER_ENABLED=true in .env"
              }
            />
          </section>
        )}

        {/* ---------------------------------------------- Pipeline */}
        <section className="rounded-3xl border border-neutral-800 bg-neutral-950 p-6 md:p-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-2xl font-bold">Pipeline</h2>
              <p className="mt-1 text-sm text-neutral-500">Jobs run in the background; this page updates live.</p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={busy.ingest || activeKinds.has("ingest")}
                onClick={() => run("ingest", startIngestJob, "News fetch started")}
                className="rounded-lg border border-neutral-700 px-4 py-2 text-sm font-semibold transition hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {activeKinds.has("ingest") ? "Fetching news…" : "Fetch latest news"}
              </button>
              <button
                type="button"
                disabled={busy.compose || activeKinds.has("compose")}
                onClick={() => run("compose", () => startComposeJob(7), "Draft generation started (takes a few minutes)")}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {activeKinds.has("compose") ? "Writing draft…" : "Generate new draft"}
              </button>
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-neutral-500">
                <tr className="border-b border-neutral-800">
                  <th className="py-2 pr-4 font-medium">Job</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Started</th>
                  <th className="py-2 pr-4 font-medium">Took</th>
                  <th className="py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.jobs || []).map((job) => (
                  <tr key={job.id} className="border-b border-neutral-900 align-top">
                    <td className="py-3 pr-4 capitalize">
                      {job.kind}
                      <span className="ml-2 text-xs text-neutral-600">#{job.id} · {job.trigger}</span>
                    </td>
                    <td className="py-3 pr-4"><Pill status={job.status} /></td>
                    <td className="py-3 pr-4 text-neutral-400">{timeAgo(job.created_at)}</td>
                    <td className="py-3 pr-4 text-neutral-400">{duration(job)}</td>
                    <td className={`py-3 ${job.status === "failed" ? "text-rose-300" : "text-neutral-300"}`}>{jobSummary(job)}</td>
                  </tr>
                ))}
                {overview && overview.jobs.length === 0 && (
                  <tr><td colSpan="5" className="py-6 text-neutral-500">No jobs yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---------------------------------------------- Issues */}
        <section className="rounded-3xl border border-neutral-800 bg-neutral-950 p-6 md:p-8">
          <h2 className="text-2xl font-bold">Issues</h2>
          <p className="mt-1 text-sm text-neutral-500">Preview a draft, send yourself a test, then publish.</p>

          <div className="mt-6 flex flex-col divide-y divide-neutral-900">
            {issues.map((issue) => {
              const sent = issue.deliveries?.sent || 0
              const failed = issue.deliveries?.failed || 0

              return (
                <article key={issue.id} className="py-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                        <Pill status={issue.status} />
                        <ScoreBadge review={issue.review} />
                        <span>#{issue.id}</span>
                        <span>· created {timeAgo(issue.created_at)}</span>
                        {issue.format === 1 && <span>· legacy format</span>}
                        {issue.stories != null && <span>· {issue.stories} stories · {issue.sources} sources</span>}
                        {issue.models?.length > 0 && <span>· {issue.models.join(", ")}</span>}
                      </div>
                      <h3 className="mt-2 truncate text-lg font-semibold">{issue.headline || issue.title}</h3>
                      {issue.status === "published" && (
                        <p className="mt-1 text-sm text-neutral-400">
                          Delivered to {sent} {failed > 0 && <span className="text-rose-300">· {failed} failed</span>}
                        </p>
                      )}
                    </div>
  
                    <div className="flex shrink-0 flex-wrap gap-2 text-sm">
                      <Link
                        to={issue.status === "published" ? `/newsletters/${issue.id}` : `/newsletters/${issue.id}?preview=1`}
                        className="rounded-lg border border-neutral-700 px-3 py-1.5 hover:border-neutral-500"
                      >
                        {issue.status === "published" ? "View" : "Preview"}
                      </Link>
  
                      <button
                        type="button"
                        disabled={busy[`test-${issue.id}`]}
                        onClick={() => run(`test-${issue.id}`, () => sendTestEmail(issue.id), (result) => result.message)}
                        className="rounded-lg border border-neutral-700 px-3 py-1.5 hover:border-neutral-500 disabled:opacity-50"
                      >
                        {busy[`test-${issue.id}`] ? "Sending…" : "Send test to me"}
                      </button>
  
                      {issue.status === "draft" && issue.format === 2 && (
                        <button
                          type="button"
                          disabled={busy[`recheck-${issue.id}`]}
                          onClick={() =>
                            run(`recheck-${issue.id}`, () => recheckIssue(issue.id), (result) => {
                              const score = result.review.score != null ? `score ${result.review.score}/10` : "checks only"
                              return `Re-checked #${issue.id}: ${score} · ${result.images_replaced} image${result.images_replaced === 1 ? "" : "s"} replaced`
                            })
                          }
                          title="Re-check images and review the draft again"
                          className="rounded-lg border border-neutral-700 px-3 py-1.5 hover:border-neutral-500 disabled:opacity-50"
                        >
                          {busy[`recheck-${issue.id}`] ? "Checking…" : "Re-check"}
                        </button>
                      )}
  
                      {issue.status === "draft" && (
                        <>
                          {/* Old-format drafts can't be published (see publishing.py). */}
                          {issue.format === 2 && (
                            <button
                              type="button"
                              onClick={() => setConfirming(issue)}
                              className="rounded-lg bg-white px-3 py-1.5 font-semibold text-black hover:bg-neutral-200"
                            >
                              Publish…
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={busy[`delete-${issue.id}`]}
                            onClick={() => {
                              if (window.confirm(`Delete draft #${issue.id}? This cannot be undone.`)) {
                                run(`delete-${issue.id}`, () => deleteDraft(issue.id), `Draft #${issue.id} deleted`)
                              }
                            }}
                            className="rounded-lg px-3 py-1.5 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </>
                      )}
  
                      {issue.status === "published" && failed > 0 && (
                        <button
                          type="button"
                          disabled={busy[`retry-${issue.id}`] || activeKinds.has("deliver")}
                          onClick={() => run(`retry-${issue.id}`, () => retryFailedDeliveries(issue.id), "Retrying failed deliveries")}
                          className="rounded-lg border border-rose-500/40 px-3 py-1.5 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"
                        >
                          Retry {failed} failed
                        </button>
                      )}
                    </div>
                  </div>
                  <ReviewPanel review={issue.review} />
                </article>
              )
            })}
            {issues.length === 0 && <p className="py-6 text-neutral-500">No issues yet. Generate a draft above.</p>}
          </div>
        </section>
      </div>

      {/* ---------------------------------------------- Publish confirmation */}
      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-neutral-700 bg-neutral-950 p-6">
            <h3 className="text-xl font-bold">Publish this issue?</h3>
            <p className="mt-3 text-neutral-300">{confirming.headline || confirming.title}</p>
            <p className="mt-4 text-sm text-neutral-400">
              It will appear in the public archive and be emailed to{" "}
              <strong className="text-white">{overview?.subscribers ?? 0} subscribers</strong>. Its stories are then
              marked as covered so future issues won't repeat them. This can't be undone.
            </p>
            {reviewFixes(confirming.review) > 0 && (
              <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                The review flagged {reviewFixes(confirming.review)} thing{reviewFixes(confirming.review) === 1 ? "" : "s"} to fix.
                Check the notes before sending.
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => setConfirming(null)} className="rounded-lg px-4 py-2 text-sm text-neutral-300 hover:text-white">
                Cancel
              </button>
              <button
                type="button"
                disabled={busy[`publish-${confirming.id}`]}
                onClick={async () => {
                  const issue = confirming
                  await run(`publish-${issue.id}`, () => publishIssue(issue.id), "Published — sending to subscribers")
                  setConfirming(null)
                }}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black hover:bg-neutral-200 disabled:opacity-50"
              >
                Publish &amp; send
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          role="status"
          className={`fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border px-4 py-3 text-sm shadow-xl ${
            toast.kind === "error"
              ? "border-rose-500/40 bg-rose-950 text-rose-200"
              : "border-neutral-700 bg-neutral-900 text-neutral-100"
          }`}
        >
          {toast.message}
        </div>
      )}
    </main>
  )
}

export default Admin
