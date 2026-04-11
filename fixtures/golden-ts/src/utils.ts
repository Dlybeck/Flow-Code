/**
 * Shared utility functions for the golden TypeScript fixture.
 */

export function formatGreeting(name: string): string {
  return `Hello, ${name}!`;
}

export function validateName(name: string): boolean {
  return name.trim().length > 0;
}
