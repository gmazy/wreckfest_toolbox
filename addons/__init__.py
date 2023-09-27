"""
Addon loader to load generic Blender addons
"""


__all__ = ["wf_shaders", "ui_bugmenu", "wf_mod_gen"] #enabled addons

def register():
    for name in __all__:
        globals()[name].register()

def unregister():
    for name in __all__:
        globals()[name].unregister()