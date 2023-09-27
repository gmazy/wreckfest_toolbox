"""
Addon loader to load generic Blender addons
"""

# Enabled addons:
__all__ = ["wf_shaders", "ui_bugmenu", 'io_import_wreckfest', "wf_mod_gen"]


def register():
    for name in __all__:
        globals()[name].register()

def unregister():
    for name in __all__:
        globals()[name].unregister()