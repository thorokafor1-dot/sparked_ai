# Shared Tools

Small, pipeline-agnostic helpers that more than one editing folder can import.

- `denoise.py`: DeepFilterNet street-noise removal for infield audio (github.com/Rikorose/DeepFilterNet). It uses the standalone `deep-filter` binary (CPU, no torch), which is downloaded to `bin/` (gitignored) on first use. Output is sample-aligned with the source (measured 0 ms lag), so it can replace a clip's audio with the same seek. Default attenuation limit is 18 dB. Full suppression sounds underwater and clashes with the smooth brand feel.

## Quality gates
- Denoised audio flows into renders that pass the normal video gates (loudness, dead air). After changing the default strength, re-render one infield edit and let those gates check it.
