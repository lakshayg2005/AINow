import { useParams } from "react-router-dom"

function NewsletterDetails() {
  const { id } = useParams()

  return (
    <main className="min-h-screen bg-black px-6 py-24 text-white">

      <article className="mx-auto max-w-3xl">

        <p className="text-sm uppercase tracking-widest text-gray-500">
          Newsletter #{id}
        </p>

        <h1 className="mt-6 text-5xl font-bold leading-tight">
          The AI industry is moving faster than ever
        </h1>

        <p className="mt-6 text-gray-500">
          August 22, 2026
        </p>

        <div className="mt-12 space-y-6 text-lg leading-8 text-gray-300">

          <p>
            Artificial intelligence continues to evolve at an incredible
            pace. New models, research breakthroughs and products are
            appearing every week.
          </p>

          <p>
            This edition of AINow brings together the developments
            that matter most and explains them without unnecessary
            technical noise.
          </p>

          <h2 className="pt-8 text-3xl font-bold text-white">
            What happened this week?
          </h2>

          <p>
            This is where the actual newsletter content will eventually
            come from our backend.
          </p>

        </div>

      </article>

    </main>
  )
}

export default NewsletterDetails