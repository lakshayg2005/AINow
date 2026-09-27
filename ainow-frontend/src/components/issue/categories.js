export const CATEGORY_STYLES = {
  model_release: { label: "Model release", badge: "bg-indigo-500/15 text-indigo-300", art: "from-indigo-600/50 via-violet-700/30 to-neutral-900" },
  product: { label: "Product", badge: "bg-sky-500/15 text-sky-300", art: "from-sky-600/50 via-cyan-800/30 to-neutral-900" },
  research: { label: "Research", badge: "bg-emerald-500/15 text-emerald-300", art: "from-emerald-600/50 via-teal-800/30 to-neutral-900" },
  policy: { label: "Policy", badge: "bg-amber-500/15 text-amber-300", art: "from-amber-600/50 via-orange-800/30 to-neutral-900" },
  safety: { label: "Safety", badge: "bg-rose-500/15 text-rose-300", art: "from-rose-600/50 via-red-900/30 to-neutral-900" },
  industry: { label: "Industry", badge: "bg-slate-400/15 text-slate-300", art: "from-slate-500/50 via-slate-800/30 to-neutral-900" },
  benchmark: { label: "Benchmark", badge: "bg-violet-500/15 text-violet-300", art: "from-violet-600/50 via-fuchsia-900/30 to-neutral-900" },
  open_source: { label: "Open source", badge: "bg-green-500/15 text-green-300", art: "from-green-600/50 via-emerald-900/30 to-neutral-900" },
  tool: { label: "Tool", badge: "bg-teal-500/15 text-teal-300", art: "from-teal-600/50 via-cyan-900/30 to-neutral-900" },
  other: { label: "News", badge: "bg-neutral-500/20 text-neutral-300", art: "from-neutral-600/50 via-neutral-800/30 to-neutral-900" },
}

export function categoryStyle(category) {
  return CATEGORY_STYLES[category] || CATEGORY_STYLES.other
}
