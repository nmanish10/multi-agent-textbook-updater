type SourceBadgeProps = {
  source?: string;
};

function normalizeSource(source?: string): string {
  if (!source) {
    return "Unknown source";
  }

  const trimmed = source.trim();
  const lower = trimmed.toLowerCase();

  if (lower.includes("openalex")) return "OpenAlex";
  if (lower.includes("arxiv")) return "arXiv";
  if (lower.includes("semantic")) return "Semantic Scholar";
  if (lower.includes("official")) return "Official source";
  if (lower.includes("openai")) return "OpenAI";
  if (lower.includes("deepmind") || lower.includes("google")) return "Google DeepMind";
  if (lower.includes("meta")) return "Meta AI";
  if (lower.includes("nature")) return "Nature";
  if (lower.includes("science")) return "Science";

  return trimmed;
}

export function SourceBadge({ source }: SourceBadgeProps) {
  return <span className="sourceBadge">{normalizeSource(source)}</span>;
}
