export interface HighlightSegment {
  text: string;
  highlighted: boolean;
}

const STOPWORDS = new Set([
  'a',
  'an',
  'and',
  'are',
  'as',
  'at',
  'be',
  'by',
  'for',
  'from',
  'in',
  'into',
  'is',
  'of',
  'on',
  'or',
  'the',
  'to',
  'was',
  'were',
  'what',
  'when',
  'where',
  'which',
  'who',
  'whom',
  'whose',
  'why',
  'with',
]);

const TOKEN_PATTERN = /[\p{L}\p{N}][\p{L}\p{N}'-]*/gu;

export function buildHighlightTerms(query: string, maxTerms = 12): string[] {
  const terms: string[] = [];
  const seen = new Set<string>();

  for (const match of query.matchAll(TOKEN_PATTERN)) {
    const term = match[0].toLocaleLowerCase();
    if (term.length <= 2 || STOPWORDS.has(term) || seen.has(term)) continue;

    seen.add(term);
    terms.push(term);
    if (terms.length >= maxTerms) break;
  }

  return terms;
}

export function splitHighlightedText(text: string, terms: string[]): HighlightSegment[] {
  const uniqueTerms = Array.from(new Set(terms.map((term) => term.trim()).filter(Boolean)));
  if (!text || uniqueTerms.length === 0) return [{ text, highlighted: false }];

  const pattern = uniqueTerms
    .sort((left, right) => right.length - left.length)
    .map(escapeRegExp)
    .join('|');
  const regex = new RegExp(pattern, 'giu');
  const segments: HighlightSegment[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(regex)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      segments.push({ text: text.slice(lastIndex, index), highlighted: false });
    }
    segments.push({ text: match[0], highlighted: true });
    lastIndex = index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), highlighted: false });
  }

  return segments.length ? segments : [{ text, highlighted: false }];
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
