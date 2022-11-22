"""
Addon loader to load generic Blender addons
"""


__all__ = ["ui_bugmenu"] #enabled addons

def register():
    for name in __all__:
        globals()[name].register()

def unregister():
    for name in __all__:
        globals()[name].unregister()