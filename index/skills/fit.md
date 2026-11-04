---
name: "fit"
description: "BKP desk mode: fit a placed DC-X story to its frame (over, short, head or deck lines). Use when the supervisor says fit, lines over, lines short, overspill, or gives a gap from the live draw."
---

# FIT (BKP desk mode)

Runs on top of `bkp` [P1]. This file sets the return.

1. **Take the gap** the supervisor gives: lines over or short, in which
   column, and whether text runs into the next element. Don't measure lines
   or characters per line from a draw or screenshot, and make no line
   predictions.
2. **Choose moves in this order:**
   1. restore filed material the edit cut;
   2. a word or two cut or added in a paragraph;
   3. split a paragraph that already holds two sentences;
   4. a sentence-length paragraph break.
   Never merge filed paragraphs to gain; it costs lines.
3. **Heads and decks:** display heads fit to the frame; decks are judged on
   the draw, not the counter. The supervisor judges both.

## Return

```
1. [para N] "old" > "new"  (-12 characters)
2. ...
```

One or two moves aimed at the gap, exact strings, character change for each.
