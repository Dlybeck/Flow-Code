/**
 * Golden TypeScript fixture — entrypoint for flowcode TS adapter tests.
 */

import { formatGreeting, validateName } from "./utils";

export function main(): void {
  const name = "World";
  if (validateName(name)) {
    const msg = formatGreeting(name);
    console.log(msg);
  }
}

function buildMessage(text: string): string {
  return `[app] ${text}`;
}

export const greet = (name: string): string => {
  const msg = formatGreeting(name);
  return buildMessage(msg);
};
