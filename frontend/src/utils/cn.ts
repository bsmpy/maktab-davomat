import clsx, { type ClassValue } from 'clsx'

/** Tiny class-name helper used by every UI primitive. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}
