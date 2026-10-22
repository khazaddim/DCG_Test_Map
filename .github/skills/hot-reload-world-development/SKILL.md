---
name: hot-reload-world-development
description: "Use when: building or revising a DearCyGui hot-reload workflow where editable scene/world definitions are reloaded without restarting the persistent UI, camera controls, or event handlers. Covers isolated candidate-module loading, complete world-bundle swaps (scene, resources, collisions, terrain, traversal, feature flags), texture/resource ownership, world locking, scene generations for telemetry, and reload failure preservation."
---

# Hot-Reloadable World Development

Use this skill for DearCyGui retained-scene experiments where world geometry,
materials, and resources need to be edited and reloaded while the UI remains
running.

## Goal

Keep the long-lived application shell stable while replacing the authored
world safely:

- The **host module** owns the `dcg.Context`, windows, viewport, controls,
  keyboard handlers, and reload action.
- The **world module** owns the editable `build_scene()` function, scene
  objects, materials, generated textures, collision/terrain/traversal builders,
  feature switches, and other resources that must change with a world reload.
- A successful reload replaces the complete world bundle at once; a failed
  reload leaves the active module, scene, resources, collisions, terrain, and
  flags untouched.

## Ownership Rule

Put every behavior or resource that must respond to an edit in the reloadable
world module.

This includes:

- `Scene3D` composition and world-object construction
- geometry constants and placement tables
- `SolidMaterial`, `ImageMaterial`, and other scene materials
- generated textures, bitmap pixel creation, and texture-size constants
- world-local helper functions and world-specific visual effects
- `build_collision_world()`, `build_terrain_surface()`, and
  `build_traversal_settings()`, so gameplay support always matches geometry
- `*_ENABLED` feature switches and `effective_world_flags()`

Keep only persistent application infrastructure in the host module:

- `dcg.Context` and window/layout construction
- `DrawInWindow3D` and its callback wiring
- camera controls, input handlers, and status UI
- reload error reporting, candidate loading, and bundle swap logic
- the world lock, scene generation counter, and telemetry wiring

Do not put a world-editable texture generator or material builder in the host.
Otherwise saving the world file and pressing Reload will rebuild the scene with
an unchanged host-owned resource, making the edit appear to have had no effect.

## Event-Loop-Safe Redraws

`DrawInWindow3D.render_now()` rebuilds projection, ordering, line occlusion,
and retained DearCyGui draw nodes. Do not call it from high-frequency input
callbacks such as sliders, resize handlers, or repeated movement handlers.
Doing so blocks DearCyGui's input dispatch: a second camera operation can move
its slider while its callback waits behind the previous synchronous rebuild.

Callbacks should mutate state and invalidate the viewport only:

```python
def set_yaw(self, sender, *_: object) -> None:
  self.viewport.set_camera(replace(self.viewport.camera, yaw_deg=float(sender.value)))

def on_resize(self, *_: object) -> None:
  self.viewport.invalidate()
```

The persistent host renders at most once per event-loop frame, after callbacks
have applied the newest state:

```python
controller = build_ui(context)
while context.running:
  controller.render_if_needed()
  context.viewport.render_frame()
```

```python
def render_if_needed(self) -> None:
  with self._world_lock:
    stats = self.viewport.render_if_needed()
    if stats is not None:
      self._update_status()
```

Guard rendering, movement, resize, and reload with the same `RLock` so a
rebuild never observes a half-swapped world (for example, a new scene with old
collisions or terrain).

This coalesces rapid camera updates into one retained-frame rebuild and keeps
the UI responsive. Use `render_now()` only for an explicit synchronous action
whose caller genuinely needs the newly rendered result immediately. Reference:
`Animation/ported_demos/town_hot_reload.py` and
`Animation/ported_demos/14_dearcygui_cpu_3d_trees.py`.

## Reload Pattern

1. The host imports the world module and builds the initial world bundle with
   the same `build_world()` used for reloads.
2. On Reload, execute the edited source into a **fresh, isolated candidate
   module**. Do not use `importlib.reload()`: it re-executes code in the active
   module's namespace, so a failed or partial reload corrupts the running
   world's globals, flags, and builders.
3. Build the complete candidate bundle — resources, scene, avatar, collisions,
   terrain, traversal settings, effective flags — plus any derived host objects
   (follow controller, clamped camera) before touching active state.
4. If anything raises, report the error and return; active state is unchanged.
5. On success, assign every bundle field, increment the scene generation, and
   reset telemetry for the new configuration.

Load the candidate from source bytes so rapid same-size edits cannot reuse
stale bytecode:

```python
def load_world_candidate(module: ModuleType) -> ModuleType:
    path = Path(module.__file__)
    spec = importlib.util.spec_from_file_location(module.__name__, path)
    candidate = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), candidate.__dict__)
    return candidate
```

Group everything that must change together into one immutable bundle:

```python
@dataclass(frozen=True)
class TownWorld:
    module: ModuleType
    road_texture: dcg.Texture | None
    scene: Scene3D
    avatar: Box3D
    collisions: CollisionWorld
    terrain: TerrainSurface | None
    traversal: TraversalSettings
    flags: dict[str, bool]


def build_world(context: dcg.Context, module: ModuleType) -> TownWorld:
    texture = module.create_road_texture(context)
    scene, avatar = module.build_scene(texture)
    return TownWorld(module, texture, scene, avatar,
                     module.build_collision_world(), module.build_terrain_surface(),
                     module.build_traversal_settings(), module.effective_world_flags())
```

Swap the whole bundle under the world lock:

```python
def reload_world(self, *_: object) -> None:
    with self._world_lock:
        try:
            candidate = build_world(self.context, load_world_candidate(self.world_module))
            follow = EdgeBandFollowController(..., terrain=candidate.terrain)
        except Exception as error:
            self.reload_status.value = f"Reload failed: {type(error).__name__}: {error}"
            traceback.print_exc()
            return

        self.world_module = candidate.module
        self.viewport.scene = candidate.scene
        self.viewport.terrain = candidate.terrain
        self.avatar = candidate.avatar
        self.road_texture = candidate.road_texture
        self.collisions = candidate.collisions
        self.terrain = candidate.terrain
        self.traversal_settings = candidate.traversal
        self.effective_flags = dict(candidate.flags)
        self.follow = follow
        self.scene_generation += 1
        if self.viewport.telemetry is not None:
            self.viewport.telemetry.set_scene(self.scene_generation, self.effective_flags)
```

## Feature Switches and Effective Flags

Expose comparison groups as module-level `*_ENABLED` booleans in the world
module and apply them only through Reload — never by mutating the active
module per frame. Dependent switches must report their effective value, so
`effective_world_flags()` derives combined flags (for example, road texturing
requires roads, terrain following requires the hill). Keep geometry,
collisions, and terrain support consistent: a disabled feature must not leave
invisible colliders or terrain behind.

The host snapshots effective flags with each successful reload and passes them,
with the new scene generation, to `RenderTelemetry.set_scene()`. This resets
the rolling profiling window so different workloads are never mixed.

## Resource Lifetime

DearCyGui textures must outlive the rendering of scenes that use them. Create
world-local textures with the persistent host `dcg.Context`, then retain them
in the controller after a successful reload. Pass them into `build_scene()` if
that function creates `ImageMaterial` instances.

For world-owned generated resources, prefer this shape:

```python
# world module
def create_road_texture(context: dcg.Context) -> dcg.Texture | None:
    if not (ROAD_ENABLED and ROAD_TEXTURE_ENABLED):
        return None
    ...

def build_scene(road_texture: dcg.Texture | None = None) -> tuple[Scene3D, Box3D]:
    ...
```

Resource builders may return `None` when their feature is disabled;
`build_scene()` must fall back to solid materials in that case.

Resources stored in a world-module global (for example, the windmill billboard
textures in `_WINDMILL_TEXTURES`) stay alive because the bundle retains its
candidate module. The previous module and its textures are released only
after the new bundle has been published.

## Rebuild, Do Not Mutate Old Instances

Rebuild all scene objects from the candidate module and replace the retained
scene. Do not mix new classes or materials from the candidate module with old
scene objects, collisions, or terrain from the previous module instance.

## Validation

After a change, check both the syntax and the actual reload contract:

```powershell
& .\.venv\Scripts\python.exe -m py_compile .\Animation\ported_demos\town_hot_reload.py .\Animation\ported_demos\town_hot_reload_world.py
```

Then run the reload, feature-switch, and failure-preservation tests:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_draw_in_window_3d_profiling.py -q
```

When adding a reload behavior, verify that a successful reload replaces every
bundle field and increments the generation, and that a failing candidate leaves
the active module, scene, resources, collisions, terrain, flags, and generation
unchanged.

World loading tests are not visibility tests. When editing authored geometry,
also follow the [painter-order geometry safety guidance](../scene-class-documentation/SKILL.md#painter-order-geometry-safety).
Intersecting room parts can trigger the renderer's existing cycle fallback even
when hot reload is working correctly. Check part clearances and camera rotations:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_open_room_hot_reload_world.py tests\test_draw_in_window_3d_profiling.py -q
```

## Reference

- Host: `Animation/ported_demos/town_hot_reload.py`
- Reloadable world: `Animation/ported_demos/town_hot_reload_world.py`
- Non-intersecting room world: `Animation/ported_demos/open_room_hot_reload_world.py`
- Profiling host variant: `Animation/ported_demos/town_hot_reload_profiling.py`
- Textured box-face example: `Animation/ported_demos/collision_two_boxes.py`
- Tests: `tests/test_draw_in_window_3d_profiling.py`
- Textured box-face example: `Animation/ported_demos/collision_two_boxes.py`
