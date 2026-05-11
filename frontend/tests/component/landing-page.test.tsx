import { render, screen } from "@testing-library/react";
import { CTASection } from "@/components/landing/CTASection";
import { DemoSection } from "@/components/landing/DemoSection";
import { FAQSection } from "@/components/landing/FAQSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { Footer } from "@/components/landing/Footer";
import { HeroSection } from "@/components/landing/HeroSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { UseCasesSection } from "@/components/landing/UseCasesSection";

test("renders the SaaS landing page with core conversion sections", () => {
  render(
    <>
      <HeroSection />
      <DemoSection />
      <FeaturesSection />
      <UseCasesSection />
      <PricingSection />
      <FAQSection />
      <CTASection />
      <Footer />
    </>,
  );

  expect(
    screen.getByRole("heading", {
      name: "Build AI Chatbots That Understand Your Business Data",
    }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Get Started" }).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "View Demo" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Everything a serious AI chatbot SaaS needs to earn trust and convert traffic" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Flexible plans for every stage of your AI rollout" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Start Building Your AI Chatbot Today" })).toBeInTheDocument();
});
