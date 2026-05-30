// Tiny helper for the recurring `e instanceof Error ? e.message : String(e)`
// idiom used at every `catch (e)` site that surfaces an error to the UI.
// Pure, dependency-free, easy to unit test.

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
