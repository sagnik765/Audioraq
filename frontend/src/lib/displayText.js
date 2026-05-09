export function displayAIText(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/\b[Aa]gent\s*2\b/g, 'AI Agents');
}
