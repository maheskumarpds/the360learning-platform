from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary in a template."""
    if not dictionary:
        return None
    
    try:
        return dictionary.get(key)
    except (KeyError, AttributeError):
        return None