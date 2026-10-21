## Why town hot reload was changed

The change makes reload behave like a **prepare-then-replace operation**: build a complete new world separately, and only adopt it after construction succeeds.

The user workflow is unchanged—edit the world definition and press **Reload world**.

## Why the previous approach wasn’t fully safe

Previously, the host called:

```python
candidate_module = importlib.reload(self.world_module)
```

Despite the name `candidate_module`, **`importlib.reload()` executes into the existing module’s namespace**. It does not create an independent candidate.

That created two failure risks:

1. **A failed reload could still change active configuration.**  
   Suppose an edit changes `GRID_STEP`, disables houses, and then fails while building the scene. The old scene remains visible, but the controller’s module reference may already contain the new constants and functions. Movement, geometry, and configuration could disagree.

2. **Some construction happened after replacement had started.**  
   Terrain and traversal settings were previously built after assigning the new scene and collisions. A failure there could leave a partially replaced world.

Those risks directly conflicted with the milestone requirement that failed reloads preserve the active world **and its configuration and measurement history**.

## How the new strategy works

### 1. Load an isolated candidate

`load_world_candidate` creates a new module object and executes the edited source into that new object’s dictionary.

The active module is untouched during this step. Reading and compiling source directly also avoids reusing stale bytecode after rapid same-size edits.

### 2. Build the whole candidate world

`build_world`—the function you selected—constructs:

- Textures and other world-owned resources
- Scene geometry and avatar
- Collision world
- Terrain surface
- Traversal settings
- Effective feature flags
- Initial avatar support height

It returns these together in a `TownWorld` bundle. **It does not assign them to the active viewport.**

Using that same function at startup means initial construction and reload use the same preparation path rather than maintaining two subtly different implementations.

### 3. Prepare the remaining controller state

`_reload_world` also prepares the follow controller and a camera target clamped to the candidate’s world bounds.

All of this happens inside the failure-handling block. If preparation raises an exception, the host displays the error and returns without replacing the active references.

### 4. Adopt the prepared candidate

Only after preparation succeeds does the host replace its module, scene, avatar, resources, collisions, terrain, traversal settings, and flags.

It then:

- Increments the scene generation.
- Updates the camera and invalidates the viewport.
- Resets the telemetry window for the new world.
- Lets the normal event loop perform the next render.

The world lock coordinates replacement with rendering, movement, and camera operations so those operations don’t observe the replacement halfway through.

## What stays persistent—and the limitation

The DearCyGui context, UI, handlers, and viewport remain alive. Only world state is replaced, and the active module retains its world-owned texture references.

This is **not a general-purpose transactional Python reloader**: it does not reload imported dependencies or undo arbitrary external side effects performed by world code. Its guarantee is narrower: candidate loading/construction failures do not mutate or replace the host’s active world state.

**In short:** the old approach protected the scene assignment; the new approach also protects the configuration and supporting systems that make that scene behave correctly.



# On Arbitrary code execution inside reloaded worlds

Sounds like we need some new functions that the controller can call for something like a following NPC:

**You’re right about the current host being town-specific—but we *are* re-executing the entire world Python file.** The restriction comes from how the host calls world code, not from the isolated-module reload technique.

### What actually gets reloaded

`load_world_candidate` reads, compiles, and executes the **whole file** in a fresh module namespace. That includes any functions, classes, constants, and top-level code you add.

It does **not** selectively reload only our scene classes.

The project-specific part is `build_world`: it currently expects particular builders and returns a fixed bundle of scene, avatar, collisions, terrain, and settings. That is a **world-construction contract**, not yet a general **world-behavior contract**.

### Your NPC example exposes the missing part

Currently, `_move_in_world` does this:

```text
Resolve player movement
    → update player position
    → update camera follow
    → invalidate the scene
```

There is no call into world-defined gameplay behavior. So you could add an NPC-following function to the world file, and it would load successfully—but **nothing would invoke it**.

That was also true with the previous `importlib.reload()` approach. Reloading Python definitions does not automatically connect them to movement events.

### How I would support this

I would keep the safe candidate reload, but give the loaded world ownership of its behavior as well as its geometry. The host would call a small, explicit interface—for example:

```python
# Illustrative interface, not implemented yet.
active_world.on_player_moved(previous_position, new_position)
active_world.update(dt)
```

The reloadable world could then own:

- The NPC object and its position.
- The Cartesian-distance threshold.
- Whether following is currently active.
- The movement speed and follow algorithm.
- Any additional gameplay state.

The persistent host would not need to know which NPC follows whom or which distance rule applies.

There are two useful distinctions:

| Desired behavior | World callback |
|---|---|
| NPC takes a step whenever the player moves beyond the threshold | Player-movement event |
| Crossing the threshold starts continuous NPC movement, even after the player stops | Movement event plus a timed update |

World updates would happen **before the existing render step**. They would invalidate the scene when something changes, preserving at-most-once-per-loop rendering rather than rendering inside behavior callbacks.

### Would behavior changes reload safely?

Yes: after a successful reload, the host would call the **new active world’s behavior**, alongside its new objects and state. A failed candidate would leave the old behavior and objects active.

The important rule is that the host must dispatch through the current world—not keep callbacks bound to an old world instance after replacement.

**So your concern is valid:** the implementation currently supports reloadable *world construction* better than reloadable *gameplay*. The next extension should make behavior world-owned, rather than adding NPC-specific logic to the host. We don’t need to abandon isolated loading to do that.