# Hokm Platform — Visual & Product Direction

The master spec (Section 90-94) forbids generic AI-generated styling, glassmorphism,
neon/glow, gold "premium" looks, and stereotype-heavy Iranian decoration. Below I
document the alternatives I considered and the direction I selected, plus the
resulting design system. This is the reasoning behind `apps/mini-app/src/styles.css`.

## 1. Understanding the product

Hokm is a social, competitive 4-player trick-taking game. The table is the whole
product: your cards, the trump, the current trick, the score, and who's turn.
Everything else is a supporting surface. The UI must be fast to read at a glance,
mobile-first, and not distract from the table.

## 2. Alternatives considered (3-5 directions)

1. **"Guarded Court" / ديوان** *(selected)* — Editorial, flat, warm paper + ink +
   a single vermilion accent; high contrast; strong Persian typography; the table
   is center stage. Feels like a hand-set game journal of a serious club.
2. **"Night Table"** — Deep green felt + chalk accents, a real casino-table mood.
   Risk: reads as "generic card game" and drifts toward glass/gradient clichés.
3. **"Modern Iranian editorial"** — Persian grid paper, restrained geometric
   ornaments used sparingly as page furniture, not decoration. Strong branding,
   but risks the "calligraphy everywhere" stereotype unless heavily edited.
4. **"Sport broadcast"** — Bold color-blocked team banners, big scoreboard
   numerals, live-match energy. Great for competition, but risks looking like a
   sports app rather than a card game.
5. **"Minimal brutalism"** — Pure type + flat blocks, near-zero ornament. Clean but
   can feel cold and lose the game's warmth/social character.

## 3. Comparison & selection

| Direction | Usability | Originality | Brand | Mobile-suitability | Game-clarity | Iranian-relevance | Extensible |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Guarded Court | 5 | 4 | 5 | 5 | 5 | 4 (subtle) | 5 |
| Night Table | 4 | 3 | 3 | 4 | 4 | 2 | 4 |
| Modern Iranian | 4 | 5 | 5 | 4 | 3 | 5 | 3 |
| Sport broadcast | 4 | 4 | 4 | 4 | 4 | 3 | 5 |
| Minimal brutalism | 4 | 4 | 4 | 4 | 4 | 2 | 4 |

**Selected: "Guarded Court"** — it optimises for gameplay clarity (the #1 job of
a game table) while staying original and warm, and it lets Iranian identity live
through typography and a respectful, intentional palette rather than decoration.

## 4. Design system (encoded in CSS)

- **Palette:** warm paper (`#f4efe6`), ink (`#1d1a16`), one vermilion accent
  (`#c02b2b`) for trump/primary action; team identity is **deep teal (A)** and
  **deep violet (B)**. Team is also distinguished by *shape/position*, not color
  alone (accessibility).
- **Typography:** a Persian humanist sans (Vazirmatn) — no script ornament overload.
- **Surfaces:** flat panels, 1-2px solid borders, a single hard "drop shadow" used
  only to signal the current player's elevated state. **No gradients, no glow,
  no glassmorphism, no gold.**
- **Cards:** flat, white, high-contrast rank+suit; red for hearts/diamonds, dark
  for spades/clubs; selection lifts the card; illegal cards are dimmed.
- **Game table:** score bar at top, trump badge, opponent/partner seat pills
  (current player is filled + inverted), central trick zone, then your hand.
  The hand is the largest interactive region.
- **Motion:** short, purposeful transitions (card lift, press-down buttons) that
  communicate state — never decorative loops.

## 5. Rules the design must obey

- Touch targets ≥ 44×44 CSS px for primary controls.
- Information is never conveyed by color alone (team + position + labels).
- The server is authoritative — all "state" the UI shows is a projection.
