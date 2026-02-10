export const CONCEPT_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  definition: { bg: "bg-blue-100", text: "text-blue-700", dot: "bg-blue-500" },
  theorem: { bg: "bg-purple-100", text: "text-purple-700", dot: "bg-purple-500" },
  process: { bg: "bg-green-100", text: "text-green-700", dot: "bg-green-500" },
  concept: { bg: "bg-orange-100", text: "text-orange-700", dot: "bg-orange-500" },
  example: { bg: "bg-amber-100", text: "text-amber-700", dot: "bg-amber-500" },
  formula: { bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" },
};

export function getConceptColor(category: string) {
  return CONCEPT_COLORS[category] ?? CONCEPT_COLORS.concept;
}
