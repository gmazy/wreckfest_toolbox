import bpy
from bpy.utils import register_class, unregister_class

CLASSES = [
    ("preferences", ["WreckfestToolboxAddonPreference", "WreckfestPanelContext"]),
    ("utils.wreckfest_custom_parts_properties", ["CustomPartsProperties"]),
    ("utils.export_bgo", ["WFTB_OP_export_bgo_with_dialog", "WFTB_OP_export_bgo"]),
    ("utils.material_node", ["WreckfestWrapperNode", ]),
    ("operators.wreckfest_properties_operators", ["WreckfestCustomDataGroup", "WFTB_OT_toggle_wreckfest_custom_data"]),
    ("operators.wreckfest_physical_material_operator", ["WFTB_OT_set_physical_material", ]),
    ("operators.wreckfest_custom_parts_operators", [
        "WFTB_OT_use_custom_parts",
        "WFTB_OT_refresh_custom_parts_manager",
        "WFTB_OT_set_custom_part",
        "WFTB_OT_swith_custom_part"]
     ),
    ("ui.menus", ["WFTB_PT_wreckfest_toolbox_panel",
                  "WFTB_PT_wreckfest_material_panel",
                  "WFTB_MT_object_context_menu"])
]


def register_classes(classlists, debug=False):
    classes = []

    for fr, imps in classlists:
        impline = "from .%s import %s" % (fr, ", ".join([i for i in imps]))
        classline = "classes.extend([%s])" % (", ".join([i for i in imps]))

        exec(impline)
        exec(classline)

    for c in classes:
        if debug:
            print("REGISTERING", c)

        register_class(c)

    return classes


def unregister_classes(classes, debug=False):
    for c in classes:
        if debug:
            print("UN-REGISTERING", c)

        unregister_class(c)


def register_menus():
    bpy.types.VIEW3D_MT_object_context_menu.append(object_context_menu)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister_menus():
    bpy.types.VIEW3D_MT_object_context_menu.remove(object_context_menu)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


def object_context_menu(self, context):
    self.layout.separator()
    self.layout.menu("WFTB_MT_object_context_menu")

def menu_func_export(self, context):
    self.layout.operator("wftb.export_bgo_with_dialog", text="Bugbear Game Object V3 (.bgo3) (toolbox)")
        
