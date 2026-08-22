function Footer() {
    return (
      <footer className="border-t border-gray-800 bg-black text-white">
        <div className="mx-auto max-w-7xl px-6 py-12">
  
          <div className="flex flex-col justify-between gap-8 md:flex-row">
  
            {/* Brand */}
            <div>
              <h2 className="text-2xl font-bold">
                AINow
              </h2>
  
              <p className="mt-3 max-w-sm text-sm leading-6 text-gray-500">
                Your concise source for the latest developments
                in artificial intelligence.
              </p>
            </div>
  
            {/* Links */}
            <div className="flex gap-12">
              <div>
                <h3 className="text-sm font-semibold">
                  Explore
                </h3>
  
                <div className="mt-4 space-y-3 text-sm text-gray-500">
                  <a href="/" className="block hover:text-white">
                    Home
                  </a>
  
                  <a href="/about" className="block hover:text-white">
                    About
                  </a>
  
                  <a href="/newsletters" className="block hover:text-white">
                    Newsletters
                  </a>
                </div>
              </div>
  
              <div>
                <h3 className="text-sm font-semibold">
                  Connect
                </h3>
  
                <div className="mt-4 space-y-3 text-sm text-gray-500">
                  <a href="/contact" className="block hover:text-white">
                    Contact
                  </a>
  
                  {/* <a href="/feedback" className="block hover:text-white">
                    Feedback
                  </a> */}
                </div>
              </div>
            </div>
  
          </div>
  
          <div className="mt-12 border-t border-gray-800 pt-6 text-sm text-gray-600">
            © 2026 AINow. All rights reserved.
          </div>
  
        </div>
      </footer>
    )
  }
  
  export default Footer