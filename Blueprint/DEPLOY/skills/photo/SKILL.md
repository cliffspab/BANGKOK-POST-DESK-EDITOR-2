---

name: photo

description: "BKP desk mode: standalone photo or mugshot job (head plus caption, or NAME: caption). Use when the supervisor says photo, gives a Pix/Stand/St slug, or pastes a picture with a caption."

---
<!-- 301026_gpt_bkp3-1 -->

Runs on top of the shared edit method bundled with the installed skill or named by the selected deployment: its House Essentials, [P1] fit and [P2] verification apply. This file alone holds the photo method and return.

Pictures arrive pasted into the chat or in the DC-X Images tab. Take the asset slug (e.g. `19St-P1b`), the head budget and any inline directives (`###head`, `Standcap photo:`), and isolate the caption copy.

1. **Look at the picture** before writing anything that claims what it shows. The agency metadata caption and credit are support, not authority on spelling. When no image is available, caption only from the filing and note the limitation.
2. **Head:** short, sharp, sentence case, fitted to the head budget within ±2 (no code). Wit for soft pictures, sombre for hard news; one idea the picture and the caption both earn. Drop "Thai" from the home government or prime minister unless another country's equivalent is in frame.
3. **Caption:** simple present; Directory conversions and name conventions, with titles and offices checked under [P2]; wire bloat (`FILE PHOTO`, datelines) stripped; same name forms as any linked story; dates relative to publication day. Identity, action, location, emotion and cause need support from the image or filing. Keep the final agency attribution, with the credit last as `Photo: Firstname Lastname` or `Photo: Agency`. Lead-in captions take `LEAD-IN: caption`.
4. **Mugshots:** `NAME: caption` with no honorific, representing action or voice (`Saranwut: Violated voting rules`; `Sakhan: Locals should play role`; `Thamanat: Eyeing Agriculture Ministry`). Use simple present for active developments, past tense where present reads unnaturally, or the -ing participle for ongoing or future campaigns. Slots vary (some one short line of about 28–30 characters, others two); fit to the counter and watch trailing spaces and the drop on paste.

## Return

```text
[Head]
[Caption. Photo: Credit]
```

Then two alternate heads as plain text, one per line, nothing else on the line; both meet the supplied head budget within ±2. Then a one-line style note only if something changed materially. End there: no offer of further work or follow-up question.

A mugshot returns its `NAME: caption` in a code block on its own, with a style note only when an intervention, limitation or query needs recording.
