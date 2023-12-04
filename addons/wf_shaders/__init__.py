# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons CC0
# https://creativecommons.org/publicdomain/zero/1.0/
#
# ##### END LICENSE BLOCK #####

bl_info = {  
    "name": "Wreckfest Shaders Append",  
    "author": "Mazay",  
    "version": (1, 2),  
    "blender": (2, 80, 0),  
    "location": "Addons: Bugmenu addon, Scne Importer",
    "category": "Node"}  

import bpy
import os

class WF_SHADERS_OT_append_wf_shaders(bpy.types.Operator):
    """Add Wreckfest shaders into current file"""
    bl_idname = "wf_shaders.append_wf_shaders"
    bl_label = "Load Node Group Shaders"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        addon_folder = os.path.dirname(os.path.realpath(__file__))
        filepath = os.path.join(addon_folder,'shaders.blend')
        if os.path.exists(filepath):
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                for group_name in data_from.node_groups:
                    if group_name not in bpy.data.node_groups.keys() and group_name+' #export' not in bpy.data.node_groups.keys():
                        print("Append node group: ", group_name)
                        data_to.node_groups += [group_name]
            # Make #pbr nodes permanent
            for group in data_to.node_groups:
                if '#pbr' in group.name:
                    group.use_fake_user = True
        return {'FINISHED'}


def register():
    bpy.utils.register_class(WF_SHADERS_OT_append_wf_shaders)

def unregister():
    bpy.utils.unregister_class(WF_SHADERS_OT_append_wf_shaders)

if __name__ == "__main__":
    register()

    # The menu can also be called from scripts
    bpy.ops.wm.call_menu(name=BUGMENU_MT_menu.bl_idname)
