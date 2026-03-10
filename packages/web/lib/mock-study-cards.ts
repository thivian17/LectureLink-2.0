import type { StudyCard } from "@/types/database";

export const MOCK_CONCEPT_CARDS: StudyCard[] = [
  {
    type: "hook",
    content: "Did you know that entropy explains why your coffee gets cold but never spontaneously heats up? The universe has a built-in preference for disorder.",
  },
  {
    type: "explain",
    title: "The Core Idea",
    content: "Entropy is a measure of the number of microscopic arrangements (microstates) that correspond to a system's macroscopic state. Higher entropy means more possible arrangements — more disorder. The Second Law of Thermodynamics says that in any natural process, the total entropy of an isolated system always increases.",
  },
  {
    type: "formula",
    formula_latex: "\\Delta S = \\frac{Q}{T}",
    formula_name: "Entropy Change (Reversible Process)",
    plain_english: "The change in entropy equals the heat transferred divided by the absolute temperature.",
    variable_breakdown: [
      { symbol: "\\Delta S", name: "Change in entropy", unit: "J/K", description: "How much disorder increases or decreases" },
      { symbol: "Q", name: "Heat transferred", unit: "J", description: "Energy flowing into or out of the system as heat" },
      { symbol: "T", name: "Absolute temperature", unit: "K", description: "Temperature in Kelvin (must be > 0)" },
    ],
    conditions: "Valid for reversible processes at constant temperature.",
  },
  {
    type: "example",
    title: "Worked Example: Melting Ice",
    setup: "A 500g ice cube melts at 0°C (273.15 K). The latent heat of fusion for water is 334 J/g. What is the entropy change?",
    steps: [
      "Calculate total heat absorbed: Q = 500 g × 334 J/g = 167,000 J",
      "Temperature is constant at T = 273.15 K",
      "Apply the formula: ΔS = Q / T = 167,000 / 273.15",
      "ΔS = 611.4 J/K",
    ],
    answer: "ΔS = 611.4 J/K — entropy increases because the ice becomes more disordered as liquid water.",
  },
  {
    type: "interactive",
    challenge_type: "calculation",
    prompt: "A cup of water (200g) absorbs 50,160 J of heat at an average temperature of 323 K. What is ΔS?",
    hint: "Just divide Q by T — the formula is ΔS = Q/T",
    answer: "155.3 J/K",
    solution_steps: [
      "Given: Q = 50,160 J, T = 323 K",
      "ΔS = Q / T = 50,160 / 323",
      "ΔS ≈ 155.3 J/K",
    ],
  },
  {
    type: "real_world",
    title: "Why This Matters",
    content: "Engineers use entropy calculations to design more efficient heat engines and refrigerators. The Carnot efficiency limit — the theoretical maximum efficiency of any engine — is entirely determined by entropy. Your car engine, power plants, and even your fridge all operate within entropy constraints.",
    domain: "Mechanical Engineering",
  },
  {
    type: "gut_check",
    question_text: "What happens to the total entropy of an isolated system during a natural process?",
    options: ["It always decreases", "It always increases or stays the same", "It stays exactly the same", "It depends on temperature"],
    correct_index: 1,
    explanation: "The Second Law of Thermodynamics states that the total entropy of an isolated system can only increase or remain constant — it never spontaneously decreases.",
  },
];

export const MOCK_NON_FORMULA_CARDS: StudyCard[] = [
  {
    type: "hook",
    content: "Every time you make a decision under uncertainty, you're using probability — even if you don't realize it.",
  },
  {
    type: "explain",
    title: "What is Conditional Probability?",
    content: "Conditional probability is the likelihood of an event occurring given that another event has already happened. It narrows the sample space — instead of considering all possible outcomes, you only consider outcomes where the condition is true.",
  },
  {
    type: "explain",
    title: "The Intuition",
    content: "Think of it like filtering. If someone tells you it rained today, the probability of traffic being bad changes. You're not looking at all days anymore — just rainy days. That filter is the condition.",
  },
  {
    type: "connection",
    title: "Links to Bayes' Theorem",
    content: "Conditional probability is the foundation of Bayes' Theorem, which lets you update your beliefs as new evidence arrives. This connects directly to machine learning, medical diagnosis, and spam filtering.",
    related_concept: "Bayes' Theorem",
  },
  {
    type: "real_world",
    title: "Medical Diagnosis",
    content: "When a doctor orders a test, they use conditional probability to interpret results. A positive test result doesn't mean you definitely have the disease — the probability depends on the base rate of the disease in the population.",
    domain: "Medicine",
  },
  {
    type: "gut_check",
    question_text: "What does conditional probability measure?",
    options: [
      "The probability of two independent events",
      "The probability of an event given another event has occurred",
      "The probability of mutually exclusive events",
    ],
    correct_index: 1,
    explanation: "Conditional probability measures the likelihood of an event under the condition that another event has already occurred.",
  },
];
