"""Read one literal setting without executing shell or expanding credentials."""


def setting(raw: str, name: str) -> str | None:
    values = [line.partition("=")[2].strip().strip('"').strip("'") for line in raw.splitlines()
              if line.startswith(name + "=")]
    if len(values) > 1:
        raise ValueError("duplicate service setting; review configuration")
    return values[0] if values else None
