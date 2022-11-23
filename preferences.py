"""Addon preferences that are saved inbetween sesions."""
import bpy
import os.path
import subprocess
import threading
from os import path


def preference_save(self, context):
    bpy.ops.wm.save_userpref()


class WreckfestPanelContext(bpy.types.PropertyGroup):
    """Properties that can be changed in panel"""
    panel_enums: bpy.props.EnumProperty(
        items=(
            ("CUSTOM_PARTS", "Custom Parts", "Manage custom parts", "PRESET", 0),
            ("EXPORT", "Export", "Export scene tools", "EXPORT", 1),
            ("SETTINGS", "Addon Settings", "Addon Settings", "PREFERENCES", 3),
        ),
        name="Addon Panels",
    )


class WreckfestToolboxAddonPreference(bpy.types.AddonPreferences):
    bl_idname = "wreckfest_toolbox"

    wreckfest_message_level = [
        ("VERBOSE", "Verbose", ""),
        ("WARNING", "Warning", ""),
        ("ERROR", "Error", "")
    ]

    physical_materials = [("default", "default", "")]

    def get_physical_materials(self, context):
        if len(self.physical_materials) > 1:
            return self.physical_materials

        self.physical_materials.clear()
        if self.wf_path is None:
            self.physical_materials.append(("default", "default", ""))
            return self.physical_materials

        directory = self.wf_path + "\\data\\scene\\surface\\"

        # Check if the default physical material exist
        if not path.exists(directory + "default.suse"):
            self.physical_materials.append(("default", "default", ""))
            return self.physical_materials

        # Get all the .SUSE files in the Wreckfest\data\scene\surface folder and generate a list of string from that
        counter = 0
        for filename in os.listdir(directory):
            if filename.endswith(".suse"):
                # add the file to the material list
                material_name = os.path.splitext(os.path.basename(filename))[0]
                material = (material_name, material_name, material_name)
                self.physical_materials.append(material)
                counter += 1

        return self.physical_materials

    # Wreckfest path
    wf_path: bpy.props.StringProperty(
        name="Wreckfest Path",
        subtype="DIR_PATH",
        default=R"C:\Program Files (x86)\Steam\steamapps\common\Wreckfest",
        update=preference_save,
    )

    # Build assets tool path
    wf_build_asset_subpath: bpy.props.StringProperty(
        name="Wreckfest Build Asset Path",
        default=R"\tools\build_asset.bat"
    )

    wf_physical_material_list: bpy.props.EnumProperty(
        name="Wreckfest Physical Material List",
        items=get_physical_materials,
        default=None
    )
    # TODO : Make this update function work
    # update=bpy.ops.wftb.set_physical_material()

    export_message_level: bpy.props.EnumProperty(
        name="Export Message Level",
        items=wreckfest_message_level,
    )

    apply_modifiers: bpy.props.BoolProperty(
        name="Apply Modifier",
        default=True,
        description="Apply modifier to the exported models"
    )

    auto_split_edge: bpy.props.BoolProperty(
        name="Split Edges",
        default=True,
        description="Add a Split edge modifier for sharp edges (marked) on export"
    )

    bake_animation: bpy.props.BoolProperty(
        name="Bake Animation",
        description="Automatically add one keyframe for each frame. "
                    "Disable this to set frames yourself or to use Wreckfest's interpolation",
        default=True
    )

    build_bmap: bpy.props.BoolProperty(
        name="Build Bmap",
        description="Build .bmap textures using bimage.exe",
        default=True
    )

    build_after_export: bpy.props.BoolProperty(
        name="Build After Export",
        description="Launch the Build Asset Script in background "
                    "for the newly exported .bgo3 file once the export is done",
        default=True
    )

    def draw(self, context):
        row = self.layout.row(align=True)
        row.prop(self, "wf_path")

    @staticmethod
    def popen_and_call(on_exit, popen_args):
        """
        Runs the given args in a subprocess.Popen, and then calls the function
        on_exit when the subprocess completes.
        on_exit is a callable object, and popen_args is a list/tuple of args that
        would give to subprocess.Popen.
        """

        def run_in_thread(on_exit_event, popen_args_list):
            proc = subprocess.Popen(popen_args_list, shell=True)
            proc.wait()
            on_exit_event()
            return

        thread = threading.Thread(target=run_in_thread, args=(on_exit, popen_args))
        thread.start()
        # returns immediately after the thread starts
        return thread
