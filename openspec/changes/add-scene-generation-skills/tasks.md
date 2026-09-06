## 1. Capability Definitions

Deliverables: documented capability boundaries, a selected intermediate recipe schema format, and a defined allowed vocabulary for primitives, materials, and archetypes.

- [x] 1.1 Finalize the capability boundaries for scene generation, surface art recipes, and example cataloging against the current framework object inventory
- [x] 1.2 Choose and document the intermediate schema format for scene recipes and facade-art recipes
- [x] 1.3 Define the allowed primitive, material, and archetype vocabulary that generated outputs may reference

## 2. Class Documentation Skills

Deliverables: repo-local documentation skills for all application-level scene-authoring classes, targeted documentation for supporting utilities used directly by demos 11, 14, and 15, in-code docstrings for public classes that currently lack them, plus usage guidance, key constraints, and nearby examples.

- [x] 2.1 Document each application-level class used for scene authoring in demos 11, 14, and 15, including purpose, key parameters, and when to prefer it over nearby alternatives
- [x] 2.2 Add class-local guidance on important limitations, unsupported assumptions, and safe fallback patterns for smaller models
- [x] 2.3 Link each class guide to the most relevant demos or examples that show it in practice, and add concise docstrings to the corresponding public classes where that guidance is currently missing

## 3. Demo Navigation Documentation

Deliverables: demo-by-demo documentation that helps a smaller model find the right reference when making or editing a world, plus concise inline comments in demo code blocks that explain reusable scene-building patterns.

- [ ] 3.1 Document each relevant demo or ported example with the classes, patterns, and world-building features it demonstrates
- [ ] 3.2 Add navigation guidance that maps common world-creation or world-edit requests to the most relevant demos
- [ ] 3.3 Add concise inline comments to important demo code blocks so reusable patterns such as roof builders, stacked box structures, or billboard usage remain understandable to smaller models later
- [ ] 3.4 Call out major example gaps where a feature is plausible in the framework but not yet well represented in current demos