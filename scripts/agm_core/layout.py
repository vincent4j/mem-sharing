"""Pure machine runtime paths; resolving a layout never creates anything.

The source checkout and agents table are deliberately not inputs. Python callers
may inject RuntimeLayout with the same HOME; there is no production CLI override.
"""
from dataclasses import dataclass
from pathlib import Path


class LayoutError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RuntimeLayout:
    home: Path

    def __post_init__(self):
        home = Path(self.home)
        if not home.is_absolute() or str(home) != str(home.absolute()) or ".." in home.parts:
            raise LayoutError("runtime_layout_invalid", "HOME must be an absolute normalized path")
        object.__setattr__(self, "home", home)

    @property
    def root(self):
        return self.home / ".agents-group"

    @property
    def code(self):
        return self.root / "skills/agent-group-memory"

    @property
    def var(self):
        return self.root / "var"

    @property
    def registry(self):
        return self.var / "registry.json"

    @property
    def lock(self):
        return self.var / ".agm.lock"

    @property
    def transaction_lock(self):
        return self.lock / "transaction"

    @property
    def backups(self):
        return self.root / "backups"

    def describe(self):
        return {name: str(getattr(self, name)) for name in
                ("root", "code", "registry", "lock", "transaction_lock", "backups")}

    def validate_paths(self):
        # HOME is the environment's anchor: e.g. macOS /var may itself resolve
        # through /private/var. Refuse only links in the managed chain below it,
        # including each leaf, without resolving or rejecting HOME's ancestry.
        for path in (self.root, self.var, self.registry, self.lock, self.transaction_lock, self.backups):
            component = self.home
            for part in path.relative_to(self.home).parts:
                component = component / part
                if component.is_symlink():
                    raise LayoutError("runtime_path_conflict", "Runtime symlink path: " + str(component))
        for path in (self.root, self.var, self.backups):
            if path.exists() and not path.is_dir():
                raise LayoutError("runtime_path_conflict", "Expected runtime directory: " + str(path))


def resolve_layout(home=None):
    return RuntimeLayout(Path.home() if home is None else Path(home))


def from_request(request):
    # Requests must carry HOME. An omitted test HOME must never fall back to the host.
    if not request.get("home"):
        raise LayoutError("runtime_layout_invalid", "request.home is required")
    layout = request.get("runtime_layout") or resolve_layout(request["home"])
    if not isinstance(layout, RuntimeLayout) or layout.home != Path(request["home"]):
        raise LayoutError("runtime_layout_invalid", "Injected layout must match request.home")
    layout.validate_paths()
    return layout
