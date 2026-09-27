import { useState } from "react"
import {
  Badge,
  CategoryBadge,
  Citations,
  CoverImage,
  Engagement,
  WhyItMatters,
} from "./ui"

function highlightRing(active) {
  return active
    ? "ring-2 ring-indigo-400 ring-offset-4 ring-offset-black"
    : "ring-0"
}

// ============================================================
// Quick News
// ============================================================

export function QuickNewsCard({ card, sources, featured = false, highlighted }) {
  return (
    <article
      id={`story-${card.story_id}`}
      className={`group scroll-mt-32 overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950 transition hover:border-neutral-600 ${highlightRing(highlighted)} ${featured ? "md:col-span-2 md:grid md:grid-cols-2" : ""}`}
    >
      <CoverImage
        src={card.image_url}
        alt={card.headline}
        category={card.category}
        className={featured ? "aspect-[16/10] md:aspect-auto md:h-full" : "aspect-[16/9]"}
      />

      <div className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={card.category} />
          {card.is_update && <Badge className="bg-orange-500/15 text-orange-300">Update</Badge>}
        </div>

        <h3 className={`font-bold leading-snug text-white ${featured ? "text-2xl md:text-3xl" : "text-xl"}`}>
          {card.headline}
        </h3>

        <p className="text-[15px] leading-7 text-neutral-400">{card.summary}</p>

        <WhyItMatters text={card.why_it_matters} />

        <div className="mt-auto flex flex-col gap-3 border-t border-neutral-900 pt-4">
          <Engagement engagement={card.engagement} />
          <Citations refs={card.refs} sources={sources} />
        </div>
      </div>
    </article>
  )
}

// ============================================================
// Research
// ============================================================

const RESEARCH_TABS = [
  { key: "problem", label: "Problem" },
  { key: "core_idea", label: "Idea" },
  { key: "key_result", label: "Result" },
]

function Authors({ authors }) {
  if (!authors?.length) return null

  const shown = authors.slice(0, 4).join(", ")
  return (
    <p className="text-sm text-neutral-500">
      {shown}
      {authors.length > 4 ? " et al." : ""}
    </p>
  )
}

function ResearchTabs({ card }) {
  const tabs = RESEARCH_TABS.filter((tab) => card[tab.key])
  const [active, setActive] = useState(tabs[0]?.key)

  if (!tabs.length) return null

  return (
    <div>
      <div role="tablist" className="inline-flex rounded-lg border border-neutral-800 bg-neutral-900 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            type="button"
            aria-selected={active === tab.key}
            onClick={() => setActive(tab.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              active === tab.key
                ? "bg-neutral-100 text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <p role="tabpanel" className="mt-4 min-h-[5.25rem] text-[15px] leading-7 text-neutral-300">
        {card[active]}
      </p>
    </div>
  )
}

export function ResearchCard({ card, sources, highlighted }) {
  return (
    <article
      id={`story-${card.story_id}`}
      className={`group flex scroll-mt-32 flex-col overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950 transition hover:border-neutral-600 ${highlightRing(highlighted)}`}
    >
      <CoverImage src={card.image_url} alt={card.title} category="research" className="aspect-[2/1]" />

      <div className="flex flex-1 flex-col gap-4 p-6">
        <a
          href={card.paper_url || sources[card.refs?.[0]]?.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-lg font-bold leading-snug text-white transition hover:text-indigo-200"
        >
          {card.title}
        </a>

        <Authors authors={card.authors} />
        <ResearchTabs card={card} />
        <WhyItMatters text={card.why_it_matters} />

        <div className="mt-auto flex flex-col gap-3 border-t border-neutral-900 pt-4">
          <Engagement engagement={card.engagement} />
          <Citations refs={card.refs} sources={sources} />
        </div>
      </div>
    </article>
  )
}

export function PaperOfTheWeek({ card, sources, highlighted }) {
  return (
    <article
      id={`story-${card.story_id}`}
      className={`group scroll-mt-32 overflow-hidden rounded-3xl border border-indigo-500/40 bg-gradient-to-br from-indigo-950/60 via-neutral-950 to-neutral-950 ${highlightRing(highlighted)}`}
    >
      <div className="grid md:grid-cols-5">
        <CoverImage
          src={card.image_url}
          alt={card.title}
          category="research"
          className="aspect-[16/10] md:col-span-2 md:aspect-auto md:h-full"
        />

        <div className="flex flex-col gap-5 p-7 md:col-span-3 md:p-9">
          <Badge className="w-fit bg-indigo-400/20 text-indigo-200">★ Paper of the week</Badge>

          <a
            href={card.paper_url || sources[card.refs?.[0]]?.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-2xl font-bold leading-tight text-white transition hover:text-indigo-200 md:text-3xl"
          >
            {card.title}
          </a>

          <Authors authors={card.authors} />

          <dl className="grid gap-4">
            {RESEARCH_TABS.filter((tab) => card[tab.key]).map((tab) => (
              <div key={tab.key}>
                <dt className="text-xs font-bold uppercase tracking-wider text-indigo-300">{tab.label}</dt>
                <dd className="mt-1 text-[15px] leading-7 text-neutral-300">{card[tab.key]}</dd>
              </div>
            ))}
          </dl>

          <WhyItMatters text={card.why_it_matters} />

          <div className="flex flex-col gap-3 border-t border-indigo-500/20 pt-4">
            <Engagement engagement={card.engagement} />
            <Citations refs={card.refs} sources={sources} />
          </div>
        </div>
      </div>
    </article>
  )
}

// ============================================================
// Deep Dive
// ============================================================

function readingMinutes(card) {
  const text = [card.introduction, ...card.sections.map((section) => section.body)].join(" ")
  return Math.max(1, Math.round(text.split(/\s+/).length / 220))
}

export function DeepDive({ card, sources, highlighted }) {
  const [open, setOpen] = useState(() => new Set([0]))
  const allOpen = open.size === card.sections.length

  function toggle(index) {
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  function toggleAll() {
    setOpen(allOpen ? new Set() : new Set(card.sections.map((_, index) => index)))
  }

  return (
    <article
      id={`story-${card.story_id}`}
      className={`group scroll-mt-32 overflow-hidden rounded-3xl border border-neutral-800 bg-neutral-950 ${highlightRing(highlighted)}`}
    >
      <div className="relative">
        <CoverImage src={card.image_url} alt={card.title} category="model_release" className="aspect-[21/9]" />
        <div className="absolute inset-0 bg-gradient-to-t from-neutral-950 via-neutral-950/40 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-6 md:p-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-300">
            Deep dive · {readingMinutes(card)} min read
          </p>
          <h3 className="mt-3 max-w-3xl text-3xl font-bold leading-tight text-white md:text-5xl">{card.title}</h3>
        </div>
      </div>

      <div className="mx-auto max-w-3xl p-6 md:p-10">
        <p className="text-lg leading-8 text-neutral-200 first-letter:float-left first-letter:mr-3 first-letter:text-6xl first-letter:font-bold first-letter:leading-none first-letter:text-indigo-300">
          {card.introduction}
        </p>

        {card.sections.length > 0 && (
          <div className="mt-10">
            <div className="mb-3 flex justify-end">
              <button type="button" onClick={toggleAll} className="text-sm text-neutral-400 hover:text-white">
                {allOpen ? "Collapse all" : "Expand all"}
              </button>
            </div>

            <div className="divide-y divide-neutral-800 border-y border-neutral-800">
              {card.sections.map((section, index) => {
                const isOpen = open.has(index)

                return (
                  <section key={section.heading}>
                    <button
                      type="button"
                      onClick={() => toggle(index)}
                      aria-expanded={isOpen}
                      className="flex w-full items-center justify-between py-5 text-left"
                    >
                      <span className="text-lg font-semibold text-white">{section.heading}</span>
                      <span className={`text-2xl text-neutral-500 transition-transform ${isOpen ? "rotate-45" : ""}`}>+</span>
                    </button>

                    <div className={`grid transition-all duration-300 ${isOpen ? "grid-rows-[1fr] pb-6 opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
                      <p className="overflow-hidden text-[16px] leading-8 text-neutral-300">{section.body}</p>
                    </div>
                  </section>
                )
              })}
            </div>
          </div>
        )}

        <div className="mt-8">
          <p className="mb-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Sources</p>
          <Citations refs={card.refs} sources={sources} />
        </div>
      </div>
    </article>
  )
}

// ============================================================
// Trends
// ============================================================

export function TrendCard({ index, card, sources, storyTitles, onJump }) {
  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-neutral-800 bg-gradient-to-b from-neutral-900/60 to-neutral-950 p-7">
      <span className="text-5xl font-black text-indigo-400/40">{String(index).padStart(2, "0")}</span>
      <h3 className="text-xl font-bold text-white">{card.title}</h3>
      <p className="text-[15px] leading-7 text-neutral-400">{card.explanation}</p>
      {card.evidence && <p className="text-sm leading-6 text-neutral-500">{card.evidence}</p>}

      <div className="mt-auto flex flex-wrap gap-2 pt-2">
        {card.story_ids.map((storyId) =>
          storyTitles[storyId] ? (
            <button
              key={storyId}
              type="button"
              onClick={() => onJump(storyId)}
              className="rounded-full border border-neutral-700 px-3 py-1 text-xs text-neutral-300 transition hover:border-indigo-400 hover:text-white"
            >
              ↳ {storyTitles[storyId]}
            </button>
          ) : null
        )}
      </div>

      <Citations refs={card.refs} sources={sources} />
    </article>
  )
}

// ============================================================
// Concept
// ============================================================

export function ConceptCard({ card, relatedTitle, onJump }) {
  const [mode, setMode] = useState("simple")

  return (
    <article className="overflow-hidden rounded-3xl border border-neutral-800 bg-neutral-950">
      <div className="grid md:grid-cols-5">
        <div className="relative flex min-h-48 items-end overflow-hidden bg-gradient-to-br from-fuchsia-600/40 via-indigo-700/30 to-neutral-950 p-8 md:col-span-2">
          <div className="absolute -left-10 -top-10 h-48 w-48 rounded-full bg-fuchsia-400/10 blur-3xl" />
          <h3 className="relative text-3xl font-bold leading-tight text-white md:text-4xl">{card.concept}</h3>
        </div>

        <div className="flex flex-col gap-5 p-7 md:col-span-3 md:p-9">
          <div className="inline-flex w-fit rounded-lg border border-neutral-800 bg-neutral-900 p-1">
            {[
              ["simple", "In plain words"],
              ["technical", "Under the hood"],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={mode === key}
                onClick={() => setMode(key)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  mode === key ? "bg-neutral-100 text-black" : "text-neutral-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <p className="min-h-[7rem] text-[16px] leading-8 text-neutral-200">
            {mode === "simple" ? card.simple_explanation : card.technical_explanation}
          </p>

          {card.example && (
            <div className="rounded-xl bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
              <span className="font-semibold text-white">Example: </span>
              {card.example}
            </div>
          )}

          {relatedTitle && (
            <button
              type="button"
              onClick={() => onJump(card.related_story_id)}
              className="w-fit text-sm text-indigo-300 hover:text-indigo-200"
            >
              See it in this week's story: {relatedTitle} →
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

// ============================================================
// Resources
// ============================================================

export function ResourceCard({ card, highlighted }) {
  return (
    <article
      id={`story-${card.story_id}`}
      className={`group flex scroll-mt-32 flex-col overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950 transition hover:border-neutral-600 ${highlightRing(highlighted)}`}
    >
      <CoverImage src={card.image_url} alt={card.name} category="tool" className="aspect-[2/1]" label={card.name} />

      <div className="flex flex-1 flex-col gap-3 p-6">
        <Badge className="w-fit bg-teal-500/15 text-teal-300">{card.resource_type}</Badge>
        <h3 className="text-lg font-bold text-white">{card.name}</h3>
        <p className="text-[15px] leading-7 text-neutral-400">{card.description}</p>

        {card.why_useful && (
          <p className="text-sm leading-6 text-neutral-300">
            <span className="font-semibold text-white">Try it if: </span>
            {card.why_useful}
          </p>
        )}

        <div className="mt-auto flex flex-col gap-4 pt-3">
          <Engagement engagement={card.engagement} />
          <a
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex w-fit items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-neutral-200"
          >
            Open {card.resource_type} →
          </a>
        </div>
      </div>
    </article>
  )
}
