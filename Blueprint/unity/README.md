# BKP 3.x Unity updater

This directory holds the guarded machinery for updating the seven permanent
native Google Docs from the generated Blueprint deployment.

The prepared source set is `301026_gpt_bkp3-1`. Its permanent root remains
`BKP 3.0 Live`, and its update order is content first — Blueprint, Edit, Check,
Photo, PR and Directory — with Boot written last as the ignition witness.
The seven document IDs and their unique `*_bkp3-0` titles are static deployment
names: advance the edition witness and guarded hashes without renaming files.

`unity-config.json` holds protected document and folder IDs plus the expected
edition and source hashes. `unity_update.py` compiles and validates the desired
set. `emit_google_requests.py` converts one reviewed projection into an atomic,
tab-scoped Google Docs request list. `emit_native_projection.py` emits a compact
projection for independent comparison. Tests live in `tests/`.

The updater fails closed on unexpected titles, parents, source hashes, edition
witnesses, list or code structure, revisions, or mixed document states. Google
credentials stay outside the repository. A production run must use fresh
revision IDs, preserve permanent Drive IDs, update Boot last and verify every
document after the write.

The Microsoft Copilot Notebook adaptation is not part of this release.
