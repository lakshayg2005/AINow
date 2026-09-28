import { useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import {
  ConceptCard,
  DeepDive,
  PaperOfTheWeek,
  QuickNewsCard,
  ResearchCard,
  ResourceCard,
  TrendCard,
} from "./cards"
import { categoryStyle } from "./categories"
import { SectionHeader } from "./ui"

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

function useReadingProgress() {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    function update() {
      const max = document.documentElement.scrollHeight - window.innerHeight
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0)
    }

    update()
    window.addEventListener("scroll", update, { passive: true })
    window.addEventListener("resize", update)

    return () => {
      window.removeEventListener("scroll", update)
      window.removeEventListener("resize", update)
    }
  }, [])

  return progress
}

function useActiveSection(ids) {
  const [active, setActive] = useState(ids[0])

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)

        if (visible[0]) setActive(visible[0].target.id)
      },
      { rootMargin: "-120px 0px -60% 0px" }
    )

    ids.forEach((id) => {
      const element = document.getElementById(id)
      if (element) observer.observe(element)
    })

    return () => observer.disconnect()
  }, [ids])

  return active
}

function IssueView({ issue, isPreview = false }) {
  const content = issue.content
  const progress = useReadingProgress()
  const [filter, setFilter] = useState("all")
  const [highlighted, setHighlighted] = useState(null)
  const [copied, setCopied] = useState(false)
  const highlightTimer = useRef(null)

  const sources = useMemo(
    () => Object.fromEntries(content.sources.map((source) => [source.id, source])),
    [content.sources]
  )

  const sections = useMemo(
    () =>
      [
        ["news", "Quick News", content.quick_news.length > 0],
        ["research", "Research", content.research_spotlight.length > 0 || content.paper_of_week],
        ["deep-dive", "Deep Dive", content.deep_dive],
        ["trends", "Trends", content.trends.length > 0],
        ["learn", "Learn", content.concept],
        ["tools", "Tools", content.resources.length > 0],
        ["take", "Our Take", content.our_take],
        ["sources", "Sources", content.sources.length > 0],
      ].filter(([, , present]) => present),
    [content]
  )

  const sectionIds = useMemo(() => sections.map(([id]) => id), [sections])
  const activeSection = useActiveSection(sectionIds)

  // Titles of stories that have a card on this page, for
  // trend/concept "jump to story" links.
  const storyTitles = useMemo(() => {
    const titles = {}
    content.quick_news.forEach((card) => { titles[card.story_id] = card.headline })
    content.research_spotlight.forEach((card) => { titles[card.story_id] = card.title })
    if (content.paper_of_week) titles[content.paper_of_week.story_id] = content.paper_of_week.title
    if (content.deep_dive) titles[content.deep_dive.story_id] = content.deep_dive.title
    content.resources.forEach((card) => { titles[card.story_id] = card.name })
    return titles
  }, [content])

  const categories = useMemo(() => {
    const present = [...new Set(content.quick_news.map((card) => card.category))]
    return present.length > 1 ? present : []
  }, [content.quick_news])

  const news = content.quick_news.filter((card) => filter === "all" || card.category === filter)

  useEffect(() => () => clearTimeout(highlightTimer.current), [])

  function jumpToStory(storyId) {
    // The story may be hidden by a category filter; clear it
    // and scroll once React has re-rendered the card.
    setFilter("all")

    requestAnimationFrame(() => {
      const element = document.getElementById(`story-${storyId}`)
      if (!element) return

      element.scrollIntoView({ behavior: "smooth", block: "center" })
      setHighlighted(storyId)
      clearTimeout(highlightTimer.current)
      highlightTimer.current = setTimeout(() => setHighlighted(null), 2200)
    })
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const stats = content.stats

  return (
    <main className="min-h-screen bg-black text-white">
      <div
        className="fixed left-0 top-0 z-50 h-1 bg-gradient-to-r from-indigo-500 via-violet-400 to-fuchsia-400 transition-[width] duration-150"
        style={{ width: `${progress * 100}%` }}
        aria-hidden="true"
      />

      {isPreview && (
        <div className="bg-amber-400 px-6 py-2 text-center text-sm font-semibold text-black">
          Draft preview — this issue ({issue.status}) is not published yet.
        </div>
      )}

      {/* ---------------------------------------------- Hero */}
      <header className="relative overflow-hidden border-b border-neutral-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.25),transparent_60%)]" />

        <div className="relative mx-auto max-w-6xl px-6 pb-14 pt-10 md:pb-20">
          <Link to="/newsletters" className="text-sm text-neutral-400 hover:text-white">
            ← All issues
          </Link>

          <div className="mt-10 flex flex-wrap items-center gap-3 text-sm text-neutral-400">
            <span className="rounded-full border border-neutral-800 px-3 py-1">{content.title.split("—")[0].trim()}</span>
            <span>{formatDate(issue.published_at || content.issue_date)}</span>
          </div>

          <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[1.05] tracking-tight md:text-6xl">
            {content.headline || content.title}
          </h1>

          {content.intro && (
            <p className="mt-6 max-w-3xl text-lg leading-8 text-neutral-300 md:text-xl">{content.intro}</p>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-neutral-500">
            {stats.items_scanned > 0 && <span>{stats.items_scanned.toLocaleString()} items scanned</span>}
            {stats.stories_considered > 0 && <span>{stats.stories_considered} stories ranked</span>}
            {stats.sources_used > 0 && <span>{stats.sources_used} sources cited</span>}
            <button
              type="button"
              onClick={copyLink}
              className="rounded-lg border border-neutral-800 px-3 py-1.5 text-neutral-300 transition hover:border-neutral-600 hover:text-white"
            >
              {copied ? "Link copied ✓" : "Copy link"}
            </button>
          </div>
        </div>
      </header>

      {/* ---------------------------------------------- Section nav */}
      <nav className="sticky top-0 z-40 border-b border-neutral-900 bg-black/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-6 py-3 [scrollbar-width:none]">
          {sections.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition ${
                activeSection === id ? "bg-white text-black" : "text-neutral-400 hover:text-white"
              }`}
            >
              {label}
            </a>
          ))}
        </div>
      </nav>

      <div className="mx-auto flex max-w-6xl flex-col gap-24 px-6 py-16">
        {/* ------------------------------------------ Quick News */}
        {content.quick_news.length > 0 && (
          <section id="news" className="scroll-mt-24">
            <SectionHeader eyebrow="Know" title="Quick News" description="The stories that mattered most this week, ranked by coverage and discussion.">
              {categories.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {["all", ...categories].map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setFilter(category)}
                      aria-pressed={filter === category}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                        filter === category
                          ? "border-white bg-white text-black"
                          : "border-neutral-800 text-neutral-400 hover:border-neutral-600 hover:text-white"
                      }`}
                    >
                      {category === "all" ? "All" : categoryStyle(category).label}
                    </button>
                  ))}
                </div>
              )}
            </SectionHeader>

            <div className="grid gap-6 md:grid-cols-2">
              {news.map((card, index) => (
                <QuickNewsCard
                  key={card.story_id}
                  card={card}
                  sources={sources}
                  featured={filter === "all" && index === 0}
                  highlighted={highlighted === card.story_id}
                />
              ))}
            </div>
          </section>
        )}

        {/* ------------------------------------------ Research */}
        {(content.paper_of_week || content.research_spotlight.length > 0) && (
          <section id="research" className="scroll-mt-24">
            <SectionHeader eyebrow="Know" title="Research Spotlight" description="Papers the community is reading, explained for builders." />

            <div className="flex flex-col gap-6">
              {content.paper_of_week && (
                <PaperOfTheWeek
                  card={content.paper_of_week}
                  sources={sources}
                  highlighted={highlighted === content.paper_of_week.story_id}
                />
              )}

              <div className="grid gap-6 md:grid-cols-3">
                {content.research_spotlight.map((card) => (
                  <ResearchCard key={card.story_id} card={card} sources={sources} highlighted={highlighted === card.story_id} />
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ------------------------------------------ Deep Dive */}
        {content.deep_dive && (
          <section id="deep-dive" className="scroll-mt-24">
            <SectionHeader eyebrow="Deep Dive" title="Story of the Week" />
            <DeepDive card={content.deep_dive} sources={sources} highlighted={highlighted === content.deep_dive.story_id} />
          </section>
        )}

        {/* ------------------------------------------ Trends */}
        {content.trends.length > 0 && (
          <section id="trends" className="scroll-mt-24">
            <SectionHeader eyebrow="Know" title="AI Trends" description="Patterns connecting this week's stories. Tap a story to jump to it." />
            <div className="grid gap-6 md:grid-cols-2">
              {content.trends.map((card, index) => (
                <TrendCard
                  key={card.title}
                  index={index + 1}
                  card={card}
                  sources={sources}
                  storyTitles={storyTitles}
                  onJump={jumpToStory}
                />
              ))}
            </div>
          </section>
        )}

        {/* ------------------------------------------ Learn */}
        {content.concept && (
          <section id="learn" className="scroll-mt-24">
            <SectionHeader eyebrow="Learn" title="Concept of the Week" />
            <ConceptCard
              card={content.concept}
              relatedTitle={storyTitles[content.concept.related_story_id]}
              onJump={jumpToStory}
            />
          </section>
        )}

        {/* ------------------------------------------ Tools */}
        {content.resources.length > 0 && (
          <section id="tools" className="scroll-mt-24">
            <SectionHeader eyebrow="Use" title="Tools & Resources" description="Trending open-source projects and models worth trying." />
            <div className="grid gap-6 md:grid-cols-3">
              {content.resources.map((card) => (
                <ResourceCard key={card.story_id} card={card} highlighted={highlighted === card.story_id} />
              ))}
            </div>
          </section>
        )}

        {/* ------------------------------------------ Our Take */}
        {content.our_take && (
          <section id="take" className="scroll-mt-24">
            <SectionHeader eyebrow="Opinion" title="Our Take" />
            <blockquote className="relative rounded-3xl border border-neutral-800 bg-neutral-950 p-8 md:p-12">
              <span className="absolute left-6 top-2 text-8xl font-serif leading-none text-indigo-400/30" aria-hidden="true">“</span>
              <p className="relative text-xl leading-9 text-neutral-200 md:text-2xl md:leading-10">{content.our_take}</p>
              <footer className="mt-6 text-sm text-neutral-500">— The AINow editors</footer>
            </blockquote>
          </section>
        )}

        {/* ------------------------------------------ Sources */}
        {content.sources.length > 0 && (
          <section id="sources" className="scroll-mt-24">
            <SectionHeader eyebrow="Transparency" title="Sources" description="Every claim above links back to one of these." />
            <ol className="grid gap-x-10 gap-y-3 md:grid-cols-2">
              {content.sources.map((source) => (
                <li key={source.id} className="flex gap-3 text-sm leading-6">
                  <span className="w-6 shrink-0 text-right font-semibold text-indigo-300">{source.id}</span>
                  <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-neutral-300 hover:text-white">
                    {source.title}
                    <span className="text-neutral-600"> — {source.source_name}</span>
                  </a>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>

      <footer className="border-t border-neutral-900 py-10 text-center text-sm text-neutral-600">
        {stats.models?.length > 0 && <p>Written with free open models ({stats.models.join(", ")}) and checked against sources.</p>}
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="mt-4 text-neutral-400 hover:text-white"
        >
          ↑ Back to top
        </button>
      </footer>
    </main>
  )
}

export default IssueView
