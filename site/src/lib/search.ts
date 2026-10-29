// Shared by the build (haystacks on film cards / calendar rows) and the browser (the typed query),
// so both sides normalize identically: lowercase, strip accents ("amélie" ≈ "amelie"), and collapse
// punctuation/quotes to spaces ("je so'" ≈ "je so’"). No Node imports — this ships to the client.
export function searchKey(...parts: unknown[]): string {
  return parts
    .filter((p) => p != null && p !== '')
    .join(' ')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}
