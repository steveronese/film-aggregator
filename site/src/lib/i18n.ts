// UI string catalogue for the client-side IT/EN language toggle (see Layout.astro).
// Pages render Italian by default; the toggle swaps [data-i18n] text, [data-en] per-element text,
// and reformats [data-date]/[data-dt] dates.
import type { Language } from './data';

export type Lang = 'it' | 'en';

export const UI: Record<Lang, Record<string, string>> = {
  it: {
    'nav.films': 'Film',
    'nav.map': 'Mappa',
    'home.title': "Cosa c'è al cinema a Milano",
    'view.films': 'Tutti i film',
    'view.venues': 'Per sala',
    'view.calendar': 'Calendario',
    'view.map': 'Mappa',
    'filter.allVenues': 'Tutte le sale',
    'filter.voOnly': 'Solo versione originale',
    'empty.films': 'Nessun film con questi filtri.',
    'empty.screenings': 'Nessuna proiezione in programma al momento.',
    'unit.film': 'film',
    'unit.films': 'film',
    'unit.screening': 'proiezione',
    'unit.screenings': 'proiezioni',
    'unit.noScreenings': 'nessuna proiezione',
    'unit.min': 'min',
    'cat.arthouse': "Sale d'essai",
    'cat.museum': 'Musei e fondazioni',
    'cat.openair': "Arene all'aperto",
    'cat.multiplex': 'Multisala',
    'map.title': 'I cinema sulla mappa',
    'map.intro': 'Tutte le sale di Milano. Premi "Trova i cinema vicino a te" per ordinarle per distanza.',
    'map.locate': 'Trova i cinema vicino a te',
    'film.originalTitle': 'Titolo originale:',
    'film.directedBy': 'regia di',
    'film.tmdb': 'Scheda su TMDB ↗',
    'film.screeningsInMilan': 'Proiezioni a Milano',
    'cinema.website': 'Sito ufficiale ↗',
    'cinema.map': 'Mappa ↗',
    'cinema.nowShowing': 'In programmazione',
    'back.films': '← Tutti i film',
    'screening.tickets': 'Biglietti',
    'screening.unrecognized': 'non riconosciuto',
    'screening.empty': 'Nessuna proiezione in programma al momento.',
    'lang.ov': 'VO',
    'lang.ov_subs': 'VO sub-ita',
    'lang.dubbed': 'ITA',
    'footer.tmdb': 'Dati dei film da TMDB. Questo prodotto usa le API di TMDB ma non è approvato né certificato da TMDB.',
    'footer.disclaimer': 'Orari e programmazione possono cambiare: verifica sempre sul sito della sala prima di andare.',
  },
  en: {
    'nav.films': 'Films',
    'nav.map': 'Map',
    'home.title': "What's on in Milan's cinemas",
    'view.films': 'All films',
    'view.venues': 'By venue',
    'view.calendar': 'Calendar',
    'view.map': 'Map',
    'filter.allVenues': 'All venues',
    'filter.voOnly': 'Original version only',
    'empty.films': 'No films match these filters.',
    'empty.screenings': 'No screenings scheduled right now.',
    'unit.film': 'film',
    'unit.films': 'films',
    'unit.screening': 'screening',
    'unit.screenings': 'screenings',
    'unit.noScreenings': 'no screenings',
    'unit.min': 'min',
    'cat.arthouse': 'Arthouse',
    'cat.museum': 'Museums & foundations',
    'cat.openair': 'Open-air',
    'cat.multiplex': 'Multiplex',
    'map.title': 'Cinemas on the map',
    'map.intro': 'All of Milan’s venues. Tap “Find cinemas near you” to sort by distance.',
    'map.locate': 'Find cinemas near you',
    'film.originalTitle': 'Original title:',
    'film.directedBy': 'directed by',
    'film.tmdb': 'View on TMDB ↗',
    'film.screeningsInMilan': 'Screenings in Milan',
    'cinema.website': 'Official site ↗',
    'cinema.map': 'Map ↗',
    'cinema.nowShowing': 'Now showing',
    'back.films': '← All films',
    'screening.tickets': 'Tickets',
    'screening.unrecognized': 'unrecognized',
    'screening.empty': 'No screenings scheduled right now.',
    'lang.ov': 'OV',
    'lang.ov_subs': 'OV subs',
    'lang.dubbed': 'Dubbed',
    'footer.tmdb': 'Film data from TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.',
    'footer.disclaimer': 'Times and programming can change — always check the venue’s own site before you go.',
  },
};

// Map a screening Language to its i18n key (for the language pill / VO badge).
export function langKey(lang: Language): string | null {
  switch (lang) {
    case 'original': return 'lang.ov';
    case 'original_subbed': return 'lang.ov_subs';
    case 'dubbed': return 'lang.dubbed';
    default: return null;
  }
}
