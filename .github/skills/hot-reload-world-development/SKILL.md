---
name: hot-reload-world-development
description: "Use when: building or revising a DearCyGui hot-reload workflow where editable scene/world definitions are reloaded without restarting the persistent UI, camera controls, or event handlers. Covers importlib reload, candidate-scene swaps, texture/resource ownership, and reload failure preservation."
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
  objects, materials, generated textures, and other resources that must change
  with a world reload.
- A successful reload atomically replaces `viewport.scene`; a failed reload
  leaves the current scene running.

## Ownership Rule

Put every behavior or resource that must respond to an edit in the reloadable
world module.

This includes:

- `Scene3D` composition and world-object construction
- geometry constants and placement tables
- `SolidMaterial`, `ImageMaterial`, and other scene materials
- generated textures, bitmap pixel creation, and texture-size constants
- world-local helper functions and world-specific visual effects

Keep only persistent application infrastructure in the host module:

- `dcg.Context` and window/layout construction
- `DrawInWindow3D` and its callback wiring
- camera controls, input handlers, and status UI
- reload error reporting and candidate-scene swap logic

Do not put a world-editable texture generator or material builder in the host.
Otherwise saving the world file and pressing Reload will rebuild the scene with
an unchanged host-owned resource, making the edit appear to have had no effect.

## Reload Pattern

1. The host imports the world module.
2. The host creates the initial world-local resources by calling world-module
   functions with the persistent `dcg.Context`.
3. The host builds the scene from those resources.
4. On Reload, invalidate import caches and reload the world module.
5. Build all candidate world-local resources and the candidate scene before
   assigning anything to the viewport.
6. If construction succeeds, replace `viewport.scene` and update references to
   the new controlled objects. If it fails, retain the old scene and show the
   error.

```python
try:
    importlib.invalidate_caches()
    candidate_module = importlib.reload(self.world_module)
    candidate_texture = candidate_module.create_road_texture(self.context)
    candidate_scene, candidate_avatar = candidate_module.build_scene(candidate_texture)
except Exception as error:
    self.reload_status.value = f"Reload failed: {type(error).__name__}: {error}"
    traceback.print_exc()
    return

self.world_module = candidate_module
self.viewport.scene = candidate_scene
self.avatar = candidate_avatar
self.road_texture = candidate_texture
```

## Resource Lifetime

DearCyGui textures must outlive the rendering of scenes that use them. Create
world-local textures with the persistent host `dcg.Context`, then retain them
in the controller after a successful reload. Pass them into `build_scene()` if
that function creates `ImageMaterial` instances.

For world-owned generated resources, prefer this shape:

```python
# world module
def create_road_texture(context: dcg.Context) -> dcg.Texture:
    ...

def build_scene(road_texture: dcg.Texture) -> tuple[Scene3D, Box3D]:
    ...

# host module, during initial build and reload
road_texture = world.create_road_texture(context)
scene, avatar = world.build_scene(road_texture)
```

## Rebuild, Do Not Mutate Old Instances

After `importlib.reload()`, rebuild all scene objects from the reloaded module
and replace the retained scene. Do not mix new classes or materials from the
reloaded module with old scene objects from the previous module instance.

## Validation

After a change, check both the syntax and the actual reload contract:

```powershell
& .\.venv\Scripts\python.exe -m py_compile .\Animation\ported_demos\town_hot_reload.py .\Animation\ported_demos\town_hot_reload_world.py
```

Then instantiate a `dcg.Context`, create the resource from the world module,
build the world, reload the module, recreate the resource, and rebuild again.
Verify the expected scene objects use the new material/resource types.

## Reference

- Host: `Animation/ported_demos/town_hot_reload.py`
- Reloadable world: `Animation/ported_demos/town_hot_reload_world.py`
- Textured box-face example: `Animation/ported_demos/collision_two_boxes.py`
