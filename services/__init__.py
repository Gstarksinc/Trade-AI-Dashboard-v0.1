import sys
from pathlib import Path
import importlib.util

class _ServiceHyphenFinder:
    def find_spec(self, fullname, path, target=None):
        parts = fullname.split(".")
        if len(parts) >= 2 and parts[0] == "services":
            sub_name = parts[1]
            hyphen_name = sub_name.replace("_", "-")
            service_dir = Path(__file__).parent / hyphen_name
            if service_dir.is_dir():
                # Submodule or package within the service
                if len(parts) == 2:
                    init_file = service_dir / "__init__.py"
                    if not init_file.exists():
                        try:
                            init_file.touch()
                        except Exception:
                            pass
                    return importlib.util.spec_from_file_location(
                        fullname,
                        str(init_file) if init_file.exists() else None,
                        submodule_search_locations=[str(service_dir)],
                    )
                else:
                    rel_parts = parts[2:]
                    target_file = service_dir.joinpath(*rel_parts[:-1], f"{rel_parts[-1]}.py")
                    if target_file.is_file():
                        return importlib.util.spec_from_file_location(fullname, str(target_file))
                    target_dir = service_dir.joinpath(*rel_parts)
                    if target_dir.is_dir():
                        init_f = target_dir / "__init__.py"
                        return importlib.util.spec_from_file_location(
                            fullname,
                            str(init_f) if init_f.exists() else None,
                            submodule_search_locations=[str(target_dir)],
                        )
        return None

if not any(isinstance(f, _ServiceHyphenFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _ServiceHyphenFinder())

