"""Simple content validation helpers for template packs."""

REQUIRED_TEMPLATE_FIELDS = {
    "encounter": ["type", "fallback_title", "possible_resolutions"],
    "item": ["type", "tags", "fallback_name", "fallback_description", "affordances"],
    "safehouse": ["name_pool", "entry_descriptions", "services"],
}

def validate_dict_templates(data: dict, kind: str) -> list[str]:
    errors = []
    required = REQUIRED_TEMPLATE_FIELDS.get(kind, [])
    for key, value in data.items():
        if not isinstance(value, dict):
            errors.append(f"{kind}.{key}: template is not dict")
            continue
        for field in required:
            if field not in value:
                errors.append(f"{kind}.{key}: missing {field}")
    return errors
