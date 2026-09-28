import { Link } from "react-router-dom"

const STEPS = [
  {
    title: "Collected continuously",
    body: "Around twenty sources are checked every few hours: lab and company blogs, research feeds, Hugging Face, GitHub, Hacker News and AI news outlets.",
  },
  {
    title: "Grouped into stories",
    body: "Articles about the same launch or paper are merged into one story, then ranked by importance, community interest, coverage and recency.",
  },
  {
    title: "Written from the sources",
    body: "Each section is written only from the retrieved source text, every card links to its sources, and sentences with numbers the sources don't contain are removed.",
  },
  {
    title: "Never repeated",
    body: "Stories from earlier issues are remembered, so a new issue only brings them back when there is a genuine update.",
  },
  {
    title: "Reviewed before sending",
    body: "Every draft is checked and read by an editor before it is published to the site and emailed to subscribers.",
  },
]

function About() {
  return (
    <div className="min-h-screen bg-black px-6 py-24 text-white">
      <div className="mx-auto max-w-5xl">
        <p className="text-sm uppercase tracking-widest text-gray-500">
          About AINow
        </p>

        <h1 className="mt-4 text-5xl font-bold">
          AI information without the noise.
        </h1>

        <p className="mt-8 max-w-3xl text-lg leading-8 text-gray-400">
          AINow is a weekly AI newsletter designed to help you stay updated
          with the latest developments in artificial intelligence without
          spending hours searching through the internet.
        </p>

        <h2 className="mt-20 text-2xl font-bold">How each issue is made</h2>

        <ol className="mt-8 grid gap-4 md:grid-cols-2">
          {STEPS.map((step, index) => (
            <li key={step.title} className="rounded-2xl border border-gray-800 p-6">
              <span className="text-sm font-medium text-gray-500">0{index + 1}</span>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 leading-7 text-gray-400">{step.body}</p>
            </li>
          ))}
        </ol>

        <div className="mt-16 flex flex-col gap-4 sm:flex-row">
          <Link
            to="/newsletters"
            className="rounded-xl bg-white px-7 py-3.5 text-center font-semibold text-black hover:bg-gray-200"
          >
            Read past issues
          </Link>
          <Link
            to="/register"
            className="rounded-xl border border-gray-700 px-7 py-3.5 text-center font-semibold hover:bg-gray-900"
          >
            Subscribe
          </Link>
        </div>
      </div>
    </div>
  )
}

export default About
