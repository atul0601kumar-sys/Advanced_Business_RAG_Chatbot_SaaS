import dynamic from "next/dynamic";
import type { Metadata } from "next";
import { HeroSection } from "@/components/landing/HeroSection";

function SectionFallback() {
  return <div className="landing-shell section-space" aria-hidden="true" />;
}

const DemoSection = dynamic(
  () => import("@/components/landing/DemoSection").then((mod) => mod.DemoSection),
  { loading: () => <SectionFallback /> },
);
const FeaturesSection = dynamic(
  () => import("@/components/landing/FeaturesSection").then((mod) => mod.FeaturesSection),
  { loading: () => <SectionFallback /> },
);
const UseCasesSection = dynamic(
  () => import("@/components/landing/UseCasesSection").then((mod) => mod.UseCasesSection),
  { loading: () => <SectionFallback /> },
);
const PricingSection = dynamic(
  () => import("@/components/landing/PricingSection").then((mod) => mod.PricingSection),
  { loading: () => <SectionFallback /> },
);
const FAQSection = dynamic(() => import("@/components/landing/FAQSection").then((mod) => mod.FAQSection), {
  loading: () => <SectionFallback />,
});
const CTASection = dynamic(() => import("@/components/landing/CTASection").then((mod) => mod.CTASection), {
  loading: () => <SectionFallback />,
});
const Footer = dynamic(() => import("@/components/landing/Footer").then((mod) => mod.Footer), {
  loading: () => <SectionFallback />,
});

export const metadata: Metadata = {
  title: "Build AI Chatbots That Understand Your Business Data",
  description:
    "Upload documents, connect your website, and launch a grounded AI chatbot with citations, analytics, and lead capture in minutes.",
  openGraph: {
    title: "Build AI Chatbots That Understand Your Business Data",
    description:
      "Production-grade RAG chatbot SaaS for customer support, sales enablement, and business knowledge retrieval.",
    type: "website",
  },
};

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <DemoSection />
      <FeaturesSection />
      <UseCasesSection />
      <PricingSection />
      <FAQSection />
      <CTASection />
      <Footer />
    </main>
  );
}
