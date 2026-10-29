// Shared by the build (haystacks on film cards / calendar rows) and the browser (the typed query),
// so both sides normalize identically: lowercase, strip accents ("amélie" ≈ "amelie"), and collapse
// punctuation/quotes to spaces ("je so'" ≈ "je so’"). No Node imports — this ships to the client.
export function searchKey(...parts: unknown[]): string {
  const norm = (p: unknown) => String(p)
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
  // Drop repeated parts (Italian, original and raw listing titles are often identical) — whole
  // parts, not words, so multi-word phrases like "la la land" still match.
  return [...new Set(parts.filter((p) => p != null && p !== '').map(norm).filter(Boolean))].join(' ');
}
