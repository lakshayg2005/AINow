import { useState } from "react"
import { categoryStyle } from "./categories"

export function Badge({ children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${className}`}
    >
      {children}
    </span>
  )
}

export function CategoryBadge({ category }) {
  const style = categoryStyle(category)
  return <Badge className={style.badge}>{style.label}</Badge>
}

/**
 * Card image with a category-tinted fallback, used when a
 * story has no picture or the image fails to load.
 */
export function CoverImage({ src, alt, category = "other", className = "aspect-[16/9]", label }) {
  const [failed, setFailed] = useState(false)
  const style = categoryStyle(category)

  if (!src || failed) {
    return (
      <div
        className={`relative flex items-end overflow-hidden bg-gradient-to-br ${style.art} ${className}`}
        role="img"
        aria-label={alt}
      >
        <div className="absolute -right-6 -top-10 h-40 w-40 rounded-full bg-white/5 blur-2xl" />
        <span className="relative m-4 text-sm font-semibold text-white/70">
          {label || style.label}
        </span>
      </div>
    )
  }

  return (
    <div className={`overflow-hidden bg-neutral-900 ${className}`}>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
      />
    </div>
  )
}

function compact(value) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`
  }
  return String(value)
}

export function Engagement({ engagement }) {
  if (!engagement) return null

  const parts = []

  if (engagement.hn_points) parts.push({ icon: "▲", text: `${compact(engagement.hn_points)} on HN`, title: "Hacker News points" })
  if (engagement.hf_upvotes) parts.push({ icon: "▲", text: `${compact(engagement.hf_upvotes)} upvotes`, title: "Hugging Face Papers upvotes" })
  if (engagement.stars) parts.push({ icon: "★", text: `${compact(engagement.stars)} stars`, title: "GitHub stars" })
  if (engagement.likes) parts.push({ icon: "♥", text: `${compact(engagement.likes)} likes`, title: "Hugging Face likes" })
  if (engagement.source_count > 1) parts.push({ icon: "◎", text: `${engagement.source_count} sources`, title: "Independent outlets covering this" })

  if (!parts.length) return null

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
      {parts.map((part) => (
        <span key={part.text} title={part.title} className="inline-flex items-center gap-1">
          <span className="text-neutral-400">{part.icon}</span>
          {part.text}
        </span>
      ))}
    </div>
  )
}

/**
 * Numbered citation chips. Hover (or focus) shows the source;
 * click opens it.
 */
export function Citations({ refs, sources }) {
  if (!refs?.length) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {refs.map((ref) => {
        const source = sources[ref]
        if (!source) return null

        return (
          <span key={ref} className="group/cite relative">
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1 text-xs text-neutral-400 transition hover:border-indigo-400/60 hover:text-indigo-200 focus:border-indigo-400/60 focus:outline-none"
            >
              <span className="font-semibold text-indigo-300">{ref}</span>
              <span className="max-w-[10rem] truncate">{source.source_name}</span>
            </a>

            <span className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 w-72 rounded-lg border border-neutral-700 bg-neutral-950 p-3 text-left text-xs leading-5 text-neutral-300 opacity-0 shadow-xl transition group-hover/cite:opacity-100 group-focus-within/cite:opacity-100">
              <span className="block font-semibold text-white">{source.title}</span>
              <span className="mt-1 block text-neutral-500">{source.source_name}</span>
            </span>
          </span>
        )
      })}
    </div>
  )
}

export function SectionHeader({ eyebrow, title, description, children }) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-400">{eyebrow}</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight text-white md:text-4xl">{title}</h2>
        {description && <p className="mt-2 max-w-2xl text-neutral-400">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export function WhyItMatters({ text }) {
  const [open, setOpen] = useState(false)

  if (!text) return null

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="inline-flex items-center gap-2 text-sm font-medium text-indigo-300 transition hover:text-indigo-200"
      >
        <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>›</span>
        Why it matters
      </button>

      <div className={`grid transition-all duration-300 ${open ? "mt-3 grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
        <p className="overflow-hidden border-l-2 border-indigo-400/60 pl-4 text-[15px] leading-7 text-neutral-300">
          {text}
        </p>
      </div>
    </div>
  )
}
