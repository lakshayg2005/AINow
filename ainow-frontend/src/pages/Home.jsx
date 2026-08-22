import Hero from "../components/Hero"
import Features from "../components/Features"
import NewsletterPreview from "../components/NewsletterPreview"
import Footer from "../components/Footer"
import { useEffect } from "react"
import { checkBackend } from "../services/api"

function Home() {
  useEffect(() => {
    checkBackend()
      .then((data) => {
        console.log("Backend response:", data)
      })
      .catch((error) => {
        console.error("Backend connection failed:", error)
      })
  }, [])
  return (
    <>
      <Hero />
      <Features />
      <NewsletterPreview />
      <Footer />
    </>
  )
}

export default Home