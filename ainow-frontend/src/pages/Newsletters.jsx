import { Link } from "react-router-dom";
const newsletters = [
  {
    id: 1,
    date: "August 22, 2026",
    category: "AI News",
    title: "The AI industry is moving faster than ever",
    description:
      "The biggest developments in artificial intelligence, from new models to major industry announcements.",
  },
  {
    id: 2,
    date: "August 15, 2026",
    category: "Research",
    title: "What's new in AI research?",
    description:
      "A quick breakdown of the research papers and breakthroughs shaping the future of AI.",
  },
  {
    id: 3,
    date: "August 8, 2026",
    category: "Generative AI",
    title: "The next generation of AI models",
    description:
      "Exploring the latest advances in generative AI and what they mean for developers and businesses.",
  },
  {
    id: 4,
    date: "August 1, 2026",
    category: "Industry",
    title: "AI is changing the tech industry",
    description:
      "The companies, products and developments making headlines across the AI ecosystem.",
  },
];

function Newsletters() {
  return (
    <main className="min-h-screen bg-black px-6 py-24 text-white">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-gray-500">
            Newsletter Archive
          </p>

          <h1 className="mt-4 text-5xl font-bold md:text-6xl">
            Previous Editions
          </h1>

          <p className="mt-6 text-lg leading-8 text-gray-400">
            Explore previous editions of AINow and catch up on the latest
            developments in artificial intelligence.
          </p>
        </div>

        {/* Newsletter Grid */}
        <div className="mt-16 grid gap-6 md:grid-cols-2">
          {newsletters.map((newsletter) => (
            <article
              key={newsletter.id}
              className="group rounded-2xl border border-gray-800 p-8 transition hover:border-gray-600"
            >
              {/* Date + Category */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">{newsletter.date}</span>

                <span className="rounded-full border border-gray-800 px-3 py-1 text-xs text-gray-400">
                  {newsletter.category}
                </span>
              </div>

              {/* Title */}
              <h2 className="mt-8 text-2xl font-bold transition group-hover:text-gray-300">
                {newsletter.title}
              </h2>

              {/* Description */}
              <p className="mt-4 leading-7 text-gray-400">
                {newsletter.description}
              </p>

              {/* Read */}
              <Link
                to={`/newsletters/${newsletter.id}`}
                className="mt-8 inline-block font-medium text-white"
              >
                Read Newsletter →
              </Link>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}

export default Newsletters;
