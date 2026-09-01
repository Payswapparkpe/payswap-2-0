/** Scroll feedback into view after the DOM updates. */
export function scrollToFeedback(element: HTMLElement | null | undefined): void {
  if (!element) {
    return;
  }
  queueMicrotask(() => {
    element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

export function normalizeName(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

/** True when two names are clearly different (not a minor spacing/case diff). */
export function namesClearlyDiffer(a: string, b: string): boolean {
  const left = normalizeName(a);
  const right = normalizeName(b);
  if (!left || !right) {
    return false;
  }
  return left !== right;
}
