function NewsletterPreview() {
    return (
      <section className="bg-black py-24 text-white">
        <div className="mx-auto max-w-7xl px-6">
  
          <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <div>
              <p className="text-sm font-semibold uppercase tracking-widest text-gray-500">
                Latest Edition
              </p>
  
              <h2 className="mt-4 text-4xl font-bold md:text-5xl">
                What's happening in AI?
              </h2>
            </div>
  
            <button className="w-fit text-gray-400 transition hover:text-white">
              View all newsletters →
            </button>
          </div>
  
          {/* Newsletter Card */}
          <div className="mt-14 overflow-hidden rounded-3xl border border-gray-800">
            
            <div className="grid md:grid-cols-2">
  
              {/* Left */}
              <div className="p-8 md:p-12">
                <span className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-400">
                  AUGUST 2026
                </span>
  
                <h3 className="mt-8 text-3xl font-bold md:text-4xl">
                  The AI industry is moving faster than ever.
                </h3>
  
                <p className="mt-6 leading-7 text-gray-400">
                  From new foundation models to groundbreaking research,
                  here's what you need to know this week.
                </p>
  
                <button className="mt-8 rounded-xl bg-white px-6 py-3 font-semibold text-black hover:bg-gray-200">
                  Read Newsletter
                </button>
              </div>
  
              {/* Right */}
              <div className="flex min-h-[350px] items-center justify-center bg-gray-900 p-10">
                <div className="text-center">
                  <div className="text-7xl font-bold">
                    AI
                  </div>
  
                  <p className="mt-3 text-gray-500">
                    Artificial Intelligence
                  </p>
                </div>
              </div>
  
            </div>
  
          </div>
  
        </div>
      </section>
    )
  }
  
  export default NewsletterPreview