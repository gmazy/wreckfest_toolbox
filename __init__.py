bl_info = {
    "name": "Wreckfest Toolbox Mz",
    "author": "Dummiesman, TheSpacebarRider, Mazay",
    "version": (1, 1, 3),
    "blender": (2, 80, 0),
    "location": "Tool Bar",
    "description": "A toolbox that help creating mods for the game Wreckfest",
    "doc_url": "https://github.com/gmazy/wreckfest_toolbox/wiki",
    "tracker_url": "https://github.com/gmazy/wreckfest_toolbox/issues",
    "support": 'COMMUNITY',
    "category": "3D View"
}

def reload_modules(name):
    import importlib

    from . import registration
    importlib.reload(registration)

    modules = []

    for entry in registration.CLASSES:
        path = entry[0].split('.')
        module = path.pop(-1)

        if(path, module) not in modules:
            modules.append((path, module))

    for path, module in modules:
        if path:
            impline = "from . %s import %s" % (".".join(path), module)
        else:
            impline = "from . import %s" % (module)

        #print("Reloading %s" % (".".join([name] + path + [module])))

        exec(impline)
        importlib.reload(eval(module))


if "bpy" in locals():
    reload_modules(bl_info['name'])

import bpy
from . import registration
from . import preferences
from nodeitems_utils import NodeItem, register_node_categories, unregister_node_categories
from nodeitems_builtins import ShaderNodeCategory
import threading
import subprocess
from .addons import *


classes = []


def register():
    global classes

    classes = registration.register_classes(registration.CLASSES)
    bpy.types.WindowManager.WFTBPanel = bpy.props.PointerProperty(
        type=preferences.WreckfestPanelContext
    )

    registration.register_menus()
    # Register Wrapper Node
    newcatlist = [ShaderNodeCategory("SH_NEW_CUSTOM", "Wreckfest", items=[NodeItem("WreckfestWrapperNode"), ]), ]
    register_node_categories("CUSTOM_NODES", newcatlist)
    addons.register()


def unregister():
    global classes

    registration.unregister_menus()

    unregister_node_categories("CUSTOM_NODES")

    del bpy.types.WindowManager.WFTBPanel

    registration.unregister_classes(classes)
    addons.unregister()
