# Briefing new work from a card

The point of the study is a new piece: its own subject, its own structure, its own forms, the reference's
style. The brief is where the style meets the subject, and it is the only file the maker gets. The order
of writing matters: subject and concept first, style second. A maker who starts from the style targets,
or from a list of the reference's devices, ends up rebuilding the reference.

```sh
python3 scripts/style.py brief style.json --for TARGET --subject "what is being made, for whom" -o brief.md
```

`TARGET` is the medium of the new work: `video`, `audio`, `text`, `image`, `slides`, `document`, `sheet`,
`ui` or `any`. It may differ from the reference's medium.

## The seven sections

1. **Subject.** What is being made, for whom, and the one thing it must say or do. From the person, never
   from the reference.
2. **Concept.** Fill it in by hand before reading on. Diverge first: three concepts from the subject, each
   with a different structure, one sentence each; then the one you take and why. Then your own list of
   parts in the order this subject needs, and the **invention ledger**: the work's own signature device,
   where the palette comes from, the type, voice or sound and the reason for it, the idea that organises
   the structure or layout, and two more things the reference never had. Each line names the part of the
   subject it grew from: its material, place, people or job. The ledger is what makes the work a sibling of
   the reference instead of a copy of it, and it is what the person sees at the end.
3. **Style targets.** In the same medium: the card's measured ranges; stay inside them without sitting on
   every median. A dimension measured once (one reference, one value) is printed as a direction with the
   band the check accepts, never as a point to hit. In another medium: the card's axes, translated into
   starting numbers for the target ([translate.md](translate.md)). The same medium gets both.
4. **Principles to carry.** The card's habits, as principles, split in two. **Core** habits are carried
   every one, each with a "Your form" line the maker fills in; in another medium, only those with a
   counterpart there, and the maker names any dropped. **Free** habits are the maker's to keep,
   bend or drop, and at least half of them are bent or dropped. The reference's components, placements,
   shapes, colour pairings and formats are not the maker's to reuse, even where one would serve a principle.
5. **Never.** The card's `avoid`, its `forbid` names, and the standing firewall: no order, opening,
   ending, set pieces, copy, footage, images, music, text or exact colours from the reference, and no
   looking at the reference, its site, its files or its source while making.
6. **Make it yours.** In the same medium, the two dimensions with the widest ranges: push both toward an
   edge on purpose. Every form is the maker's. The reference's signature devices are kept from the maker on
   purpose; a choice that feels borrowed from a known product, film, site or brand is replaced.
7. **Hand it back.** The maker reviews the work against sections 3 to 5 and hands it back with the
   brief, the filled ledger, a note of which free habits were bent or dropped, and, for a medium with no
   measuring route, its exports. The brief names no command and no file of the checker's: the person who
   wrote the brief runs `style.py check` and has the imitation review done (SKILL.md steps 5 and 6).

## Working the brief

- Write section 2 in the brief file itself, then hand the whole file over. A concept that lives only in
  your head does not reach another skill or agent.
- Make the work in a clean room: a fresh agent or subagent that gets `brief.md` and nothing else from the
  study. It never sees the references, `style.json`, `pattern.md` or the fingerprints. If you make it
  yourself, close the references and the reference's site before you start.
- Build the palette, type and sound palette fresh from the subject and the card's character (muted, warm,
  sparse). The card never holds the reference's exact values, on purpose.
- When another skill makes the work (a video, music or slides skill), give it `brief.md` as its creative
  direction, and nothing from the references themselves.
- After the first draft, run the check and the imitation review, then read the brief again: a draft that
  passes the numbers can still miss a principle the numbers cannot see, or wear a device the review names.

## Across media

A style learned from one medium can steer another: a film's pace into a deck, a song's density into a
UI's motion, an essay's rhythm into a voiceover. Only the axes travel. Measured numbers stay with their
medium: a film's 2.4 s median shot says nothing direct about a sentence. The brief prints each axis with a
starting point in the target medium. Treat those as a first guess and tune them by eye and ear.

If the new work exports to a measured medium, the check compares it on axes: each axis must sit in the same
band or the next one, and at least half must sit in the same band.

## Example (made-up)

A card learned from three calm product films (tempo medium, energy calm, space airy, colour muted, warmth
warm; core habits: movement runs sideways and slowly, words arrive by fading and never slide, one subject
holds the frame; free habits: light from a visible source, one sustained voice over room tone) briefs a
launch deck for a budgeting app:

- Three concepts: "money gets quieter" (from noise to one number); "a week in receipts" (seven days, one
  slide each); "the envelope" (one envelope opened step by step). Taken: the first, because the app's job is
  to calm, not to record.
- Invention ledger: signature, a single ruled ledger line that carries each slide's one number, drawn by
  hand, from the paper budgets the app replaces; palette from kraft paper and pencil graphite; type, a
  plain grotesque with tabular figures, because the numbers must line up; structure, noise, one number,
  three calm screens, one call to act; also a pencil-tick sound for builds and a paper texture the films
  never had.
- Principles carried in their own form: sideways movement becomes the ledger line drawing left to right;
  fading words become numbers that fade up digit by digit; one subject per frame becomes one number per
  slide. Free habits: the visible light source is dropped (no counterpart in a deck), the sustained voice
  is bent into a single held pad under the speaker notes.
- Translated targets: a slide every 8 to 20 s; one or two elements per slide with light builds; generous
  margins; muted colour with a warm accent, built fresh.
- Never: the films' product, their opening image, their colour values, their music, and no rewatching the
  films while making the deck.
