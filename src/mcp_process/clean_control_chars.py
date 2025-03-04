def fix_control_at_end(input):
    """Removes extra backslashes from control characters."""
    if not input:
        return ""
    # Replace double backslashes with single ones
    import re
    # cleaned = re.sub(r'\\\\', r'\\', control_str)
    # Replace common escaped sequences
    common_mistakes = {
        r'\n': '\n',
    }
    
    for old, new in common_mistakes.items():
        if input.endswith(old):
            input = input.replace(old, new)

    return input
