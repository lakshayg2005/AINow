function Features() {
    const features = [
      {
        number: "01",
        title: "Curated",
        description:
          "We filter through the noise and bring you the AI stories that actually matter.",
      },
      {
        number: "02",
        title: "Concise",
        description:
          "Understand complex AI developments without spending hours reading endless articles.",
      },
      {
        number: "03",
        title: "AI-Focused",
        description:
          "From research papers to industry breakthroughs, stay focused on what's happening in AI.",
      },
    ]
  
    return (
      <section className="bg-white py-24 text-black">
        <div className="mx-auto max-w-7xl px-6">
  
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-widest text-gray-500">
              Why AINow
            </p>
  
            <h2 className="mt-4 text-4xl font-bold md:text-5xl">
              AI information,
              <br />
              without the noise.
            </h2>
          </div>
  
          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.number}
                className="rounded-2xl border border-gray-200 p-8"
              >
                <span className="text-sm font-medium text-gray-400">
                  {feature.number}
                </span>
  
                <h3 className="mt-8 text-2xl font-bold">
                  {feature.title}
                </h3>
  
                <p className="mt-4 leading-7 text-gray-600">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
  
        </div>
      </section>
    )
  }
  
  export default Features