function Hero() {
    return (
      <section className="relative overflow-hidden bg-black text-white">
        <div className="mx-auto flex min-h-[85vh] max-w-7xl items-center px-6 py-24">
          
          <div className="max-w-4xl">
            {/* Small badge */}
            <div className="mb-8 inline-flex rounded-full border border-gray-700 px-4 py-2 text-sm text-gray-300">
              ✦ The AI newsletter for curious minds
            </div>
  
            {/* Main heading */}
            <h1 className="text-5xl font-bold leading-tight tracking-tight md:text-7xl">
              Stay Ahead of
              <span className="block text-gray-400">
                Artificial Intelligence.
              </span>
            </h1>
  
            {/* Description */}
            <p className="mt-8 max-w-2xl text-lg leading-8 text-gray-400 md:text-xl">
              AINow brings you the most important AI news, research,
              breakthroughs, and trends — carefully curated and simplified.
            </p>
  
            {/* Buttons */}
            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <button className="rounded-xl bg-white px-7 py-3.5 font-semibold text-black transition hover:bg-gray-200">
                Get the Newsletter →
              </button>
  
              <button className="rounded-xl border border-gray-700 px-7 py-3.5 font-semibold text-white transition hover:bg-gray-900">
                Explore Newsletters
              </button>
            </div>
  
            {/* Trust text */}
            <p className="mt-6 text-sm text-gray-500">
              No spam. Just the AI updates worth knowing.
            </p>
          </div>
  
        </div>
      </section>
    )
  }
  
  export default Hero