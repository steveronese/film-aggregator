import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// data/*.json lives at the repo root, alongside the site/ directory.
const DATA_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../data');

export type Language = 'original' | 'original_subbed' | 'dubbed' | 'unknown';

export interface Cinema {
  id: string;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  website?: string | null;
  neighborhood?: string | null;
}

export interface Film {
  tmdb_id: number;
  title: string;
  original_title?: string | null;
  italian_title?: string | null;
  year?: number | null;
  poster_path?: string | null;
  overview?: string | null;
  title_en?: string | null;
  overview_en?: string | null;
  runtime?: number | null;
  director?: string | null;
  genres: string[];
}

export interface Screening {
  cinema_id: string;
  tmdb_id: number | null;
  raw_title: string;
  start: string; // ISO local datetime
  hall?: string | null;
  language: Language;
  booking_url?: string | null;
  source_url?: string | null;
}

function load<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), 'utf-8')) as T;
}

export const getCinemas = (): Cinema[] => load<Cinema[]>('cinemas.json');
export const getFilms = (): Film[] => load<Film[]>('films.json');
export const getScreenings = (): Screening[] => load<Screening[]>('screenings.json');

export function cinemasById(): Map<string, Cinema> {
  return new Map(getCinemas().map((c) => [c.id, c]));
}

export function filmsById(): Map<number, Film> {
  return new Map(getFilms().map((f) => [f.tmdb_id, f]));
}

export function screeningsByFilm(): Map<number, Screening[]> {
  const map = new Map<number, Screening[]>();
  for (const s of getScreenings()) {
    if (s.tmdb_id == null) continue;
    (map.get(s.tmdb_id) ?? map.set(s.tmdb_id, []).get(s.tmdb_id)!).push(s);
  }
  return map;
}

export function screeningsByCinema(): Map<string, Screening[]> {
  const map = new Map<string, Screening[]>();
  for (const s of getScreenings()) {
    (map.get(s.cinema_id) ?? map.set(s.cinema_id, []).get(s.cinema_id)!).push(s);
  }
  return map;
}

// ---- presentation helpers -------------------------------------------------

export function posterUrl(p?: string | null, size: 'w185' | 'w342' | 'w500' = 'w342'): string | null {
  return p ? `https://image.tmdb.org/t/p/${size}${p}` : null;
}

export function isOriginal(lang: Language): boolean {
  return lang === 'original' || lang === 'original_subbed';
}

export function langLabel(lang: Language): string | null {
  switch (lang) {
    case 'original': return 'VO';
    case 'original_subbed': return 'VO sub-ita';
    case 'dubbed': return 'ITA';
    default: return null;
  }
}

const dayTimeFmt = new Intl.DateTimeFormat('it-IT', {
  weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
});
const dateFmt = new Intl.DateTimeFormat('it-IT', {
  weekday: 'long', day: 'numeric', month: 'long',
});
const timeFmt = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' });

export const fmtDayTime = (iso: string) => dayTimeFmt.format(new Date(iso));
export const fmtDate = (iso: string) => dateFmt.format(new Date(iso));
export const fmtTime = (iso: string) => timeFmt.format(new Date(iso));

export const dayKey = (iso: string) => iso.slice(0, 10);

export function sortByStart(list: Screening[]): Screening[] {
  return [...list].sort((a, b) => a.start.localeCompare(b.start));
}

export function groupByDay(list: Screening[]): [string, Screening[]][] {
  const groups = new Map<string, Screening[]>();
  for (const s of sortByStart(list)) {
    const k = dayKey(s.start);
    (groups.get(k) ?? groups.set(k, []).get(k)!).push(s);
  }
  return [...groups.entries()];
}
