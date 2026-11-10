# Briefing new work from a card

The point of the study is a new piece: its own subject, its own structure, the reference's style. The
brief is where the style meets the subject, and the order of writing matters: subject and concept first,
style second. A maker who starts from the style targets ends up rebuilding the reference.

```sh
python3 scripts/style.py brief style.json --for TARGET --subject "what is being made, for whom" -o brief.md
```

`TARGET` is the medium of the new work: `video`, `audio`, `text`, `image`, `slides`, `document`, `sheet`,
`ui` or `any`. It may differ from the reference's medium.

## The seven sections

1. **Subject.** What is being made, for whom, and the one thing it must say or do. From the person, never
   from the reference.
2. **Concept.** Fill it in by hand before reading on: the idea in one sentence; your own list of parts in
   the order this subject needs; one element the reference never had (a material, a motif, a viewpoint, an
   instrument, a typeface). The new element is what makes the work a sibling of the reference instead of
   a copy of it.
3. **Style targets.** In the same medium: the card's measured ranges, aim inside them. In another medium:
   the card's axes, translated into starting numbers for the target ([translate.md](translate.md)). The
   same medium gets both.
4. **Habits to keep.** The card's traits, as instructions.
5. **Never.** The card's `avoid`, its `forbid` names, and the standing firewall: no order, opening,
   ending, set pieces, copy, footage, images, music, text or exact colours from the reference.
6. **Make it yours.** In the same medium, the two dimensions with the widest ranges: the style tolerates
   the most there, so push one to an edge on purpose. Vary everything the habits do not mention.
7. **Check.** The command to run, or, for a medium with no measuring route, how to review it.

## Working the brief

- Write section 2 in the brief file itself, then hand the whole file over. A concept that lives only in
  your head does not reach another skill or agent.
- Build the palette, type and sound palette fresh from the card's character (muted, warm, sparse) and the
  subject. The card never holds the reference's exact colours, on purpose.
- When another skill makes the work (a video, music or slides skill), give it `brief.md` and `style.md`
  as its creative direction, and nothing from the references themselves.
- After the first draft, run the check, then read the brief again: a draft that passes the numbers can
  still miss a habit the numbers cannot see.

## Across media

A style learned from one medium can steer another: a film's pace into a deck, a song's density into a
UI's motion, an essay's rhythm into a voiceover. Only the axes travel. Measured numbers stay with their
medium: a film's 2.4 s median shot says nothing direct about a sentence. The brief prints each axis with a
starting point in the target medium. Treat those as a first guess and tune them by eye and ear.

If the new work exports to a measured medium, the check compares it on axes: each axis must sit in the same
band or the next one, and at least half must sit in the same band.

## Example (made-up)

A card learned from three calm product films (tempo medium, energy calm, space airy, colour muted, warmth
warm; traits: lateral camera drifts, type fades up, one subject per frame, piano and low drones) briefs a
launch deck for a budgeting app:

- Concept: "Money gets quieter." Parts: the noise of today's budgeting, one number that matters, three
  calm screens, a single call to act. New element: hand-drawn ledger lines, which no reference had.
- Translated targets: a slide every 8 to 20 s; one or two elements per slide with light builds; generous
  margins; muted colour with a warm accent, built fresh.
- Habits carried: one subject per slide, type fades in and never slides, motion only as slow lateral
  drift.
- Never: the films' product, their opening image, their colour values, their music.
