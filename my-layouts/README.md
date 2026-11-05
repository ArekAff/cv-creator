# Your own CV layouts

Drop a layout you like here, one folder per layout:

- a LaTeX CV (`.tex` plus any `.cls`/`.sty`/fonts/images), or an unzipped Overleaf project;
- or a PDF or screenshot of a CV whose look you want. Claude recreates it in LaTeX.

Then ask Claude (`/build-cv`) to use it, with any changes you want. Claude turns it into a reusable
layout: `main.tex.j2` (your design, filled from `cv.yaml`), `files/` (support files) and
`layout.yaml` (name, engine, description). After that you can select it as `my:<folder-name>`, for
example `uv run cv build --template my:anna-blue`.

How it works: `method/template-selection.md`, section 4.
