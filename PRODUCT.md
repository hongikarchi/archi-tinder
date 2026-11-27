# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Mobile web first (phone, ~390px wide); desktop is a secondary layout (`DESIGN.md` §7).

## Users

Architecture students and practitioners in Korea. They come to discover their own architectural
taste, then find people, studios and competitions that match it. Persona priority (AGENTS.md,
2026-09-17): P2 Person→Person > P1 Firm→Jobseeker > P3 Firm→Client > P4 Individual/gateway.

## Product Purpose

ArchiTinder (Archibe) turns 10–15 swipes on real buildings into a taste profile the user
recognizes as their own ("이 앱이 내 미묘한 취향을 벌써 눈치챘네?"). Success = the user feels
understood after a short session, then uses that taste to connect with others.

## Positioning

Taste is learned from swipes over a curated corpus of real buildings with precomputed embeddings,
not from a questionnaire. Two pillars: physical intuitiveness (swipe gestures that feel physical)
and magical responsiveness (the deck reacts to each swipe).

## Operating Context

Core loop: taste start (tags → cards) → swipe deck → result / persona report → save to boards.
Social: profiles, people discovery, messaging, notifications, competitions (공모전). Settings with
user-selectable themes and fonts.

## Capabilities and Constraints

- React 18 + Vite + TypeScript; styling = `tokens.css` CSS variables + CSS Modules + inline layout
  styles; no Tailwind / MUI / styled-components.
- `DESIGN.md` is the visual source of truth (4 themes, 5-step type ramp, motion tokens).
- Korean is the primary UI language; English UI is supported.
- Out of scope: dating/romance, real-estate, marketplaces, markets outside Korea, non-architecture
  industries.
- Page loads under 1s is a standing bar.

## Brand Commitments

Name: ArchiTinder / Archibe. Voice: short, friendly Korean (해요체). Single UI font family per theme
(IBM Plex Sans KR default; Noto Serif KR option).

## Evidence on Hand

Real building corpus (Make DB, `canonical_v2_buildings`, publishable rows only). No testimonials,
user counts or press exist yet; do not fabricate them.

## Product Principles

1. Honest matching over engagement metrics; never trade taste quality for swipe count.
2. Foundation correctness over feature breadth.
3. Korea-first when localization choices conflict.
4. Swipe surfaces stay uninterrupted (rapid-evaluation mode; no links on swipe cards).
5. Swipe-only decisions are core identity: no on-screen like/dislike buttons and no drag stamps/overlays
   on the swipe card (user ruling 2026-11-22). Do not propose changing the interaction model.

## Accessibility & Inclusion

Target WCAG 2.1 AA contrast in every theme. Interaction motion intentionally ignores
reduced-motion (user decision); decorative motion honors it.
