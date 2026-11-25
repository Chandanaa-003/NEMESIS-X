import { Footer } from '../components/Footer'
import { FeaturesSection } from '../components/landing/FeaturesSection'
import { FinalCtaSection } from '../components/landing/FinalCtaSection'
import { HeroSection } from '../components/landing/HeroSection'
import { HowItWorksSection } from '../components/landing/HowItWorksSection'
import { IntelligencePreviewSection } from '../components/landing/IntelligencePreviewSection'

export function HomePage() {
  return (
    <div className="bg-white text-[#111827]">
      <HeroSection />
      <IntelligencePreviewSection />
      <FeaturesSection />
      <HowItWorksSection />
      <FinalCtaSection />
      <Footer />
    </div>
  )
}
