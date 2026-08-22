function Contact() {
    return (
      <div className="min-h-screen bg-black px-6 py-24 text-white">
        <div className="mx-auto max-w-3xl">
  
          <p className="text-sm uppercase tracking-widest text-gray-500">
            Contact
          </p>
  
          <h1 className="mt-4 text-5xl font-bold">
            Let's talk.
          </h1>
  
          <p className="mt-6 text-gray-400">
            Have a question, suggestion, or idea for AINow?
            We'd love to hear from you.
          </p>
  
          <form className="mt-12 space-y-6">
  
            <input
              type="text"
              placeholder="Your name"
              className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            />
  
            <input
              type="email"
              placeholder="Your email"
              className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            />
  
            <textarea
              placeholder="Your message"
              rows="6"
              className="w-full rounded-xl border border-gray-800 bg-transparent px-5 py-4 outline-none focus:border-white"
            />
  
            <button
              type="submit"
              className="rounded-xl bg-white px-7 py-3 font-semibold text-black"
            >
              Send Message
            </button>
  
          </form>
  
        </div>
      </div>
    )
  }
  
  export default Contact