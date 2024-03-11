import bpy, pdb
from pprint import pprint
from bpy.props import (BoolProperty,)


wreckfest_property_state = [
    ("UNSET", "Unset", "", "CANCEL", 1),
    ("TRUE", "True", "", "CHECKBOX_HLT", 2),
    ("FALSE", "False", "", "CHECKBOX_DEHLT", 3)
]


class WreckfestCustomDataGroup(bpy.types.PropertyGroup):
    is_collision_model: bpy.props.EnumProperty(
        items=wreckfest_property_state, name="IsCollisionModel",
        description="Vehicle : Set the model as Collision model\n"
                    "It will not appear in game. It's used for collisionSpheres, proxies, ...\n"
                    "!! Do not use it on Solidbody or the export won't work !!"
    )
    in_visual: bpy.props.EnumProperty(
        items=wreckfest_property_state, name="vis",
        description="Track : Set the model as visible (Also known as 'InVisual')"
    )
    in_collision: bpy.props.EnumProperty(
        items=wreckfest_property_state, name="col",
        description="Track : The model is used for collisions (Also known as 'InCollision')"
    )
    otherway: bpy.props.EnumProperty(
        items=wreckfest_property_state, name="otherway", 
        description="Track : Reverse routes \nApply property to #ai_route_main"
    )
    crossstart: bpy.props.EnumProperty(
        items=wreckfest_property_state, name="crossstart", 
        description="Track : Use on alt route when alt route passes over main route start\n"
                    "Note: Remember to add proxy checkpoint to alt route"
    )
    is_test_model: bpy.props.EnumProperty(items=wreckfest_property_state, name="IsTestModel")
    is_write_model: bpy.props.EnumProperty(items=wreckfest_property_state, name="IsWriteModel")
    is_occluder: bpy.props.EnumProperty(items=wreckfest_property_state, name="IsOccluder")
    is_sprite: bpy.props.EnumProperty(items=wreckfest_property_state, name="IsSprite")
    in_stage_a: bpy.props.EnumProperty(items=wreckfest_property_state, name="InStageA")
    in_stage_b: bpy.props.EnumProperty(items=wreckfest_property_state, name="InStageB")
    in_stage_c: bpy.props.EnumProperty(items=wreckfest_property_state, name="InStageC")
    split: bpy.props.EnumProperty(items=wreckfest_property_state, name="Split")
    light_mapped: bpy.props.EnumProperty(items=wreckfest_property_state, name="LightMapped")
    vertex_color: bpy.props.EnumProperty(items=wreckfest_property_state, name="VertexColor")
    visible_to_raycast: bpy.props.EnumProperty(items=wreckfest_property_state, name="VisibleToRaycast")
    raycast_opaque: bpy.props.EnumProperty(items=wreckfest_property_state, name="RaycastOpaque")
    raycast_transparent: bpy.props.EnumProperty(items=wreckfest_property_state, name="RaycastTransparent")
    bake_vertex_ao: bpy.props.EnumProperty(items=wreckfest_property_state, name="bakeVertexAO")
    track_objects_version: bpy.props.EnumProperty(items=wreckfest_property_state, name="TrackObjectsVersion")
    trigger_group: bpy.props.EnumProperty(items=wreckfest_property_state, name="TriggerGroup")


class WFTB_OT_toggle_wreckfest_custom_data(bpy.types.Operator):
    """Set or Unset User data to define the object as a Collision model for Wreckfest"""
    bl_idname = "wftb.toggle_wreckfest_custom_data"
    bl_label = "Manage Custom Properties"
    bl_options = {'REGISTER', 'UNDO'}

    wf_props: bpy.props.PointerProperty(type=WreckfestCustomDataGroup, options={'SKIP_SAVE'})
    show_more: bpy.props.BoolProperty(name="Show More Properties", default=False)

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.prop(self.wf_props, "in_visual")
        column.prop(self.wf_props, "in_collision")
        column.prop(self.wf_props, "otherway")
        column.prop(self.wf_props, "crossstart")
        column.separator()
        column.prop(self.wf_props, "is_collision_model")
        column.separator()
        column.prop(self, 'show_more', icon='HIDE_OFF')
        if self.show_more:
            box = column.column()
            box.separator()
            box.prop(self.wf_props, "is_test_model")
            box.prop(self.wf_props, "is_write_model")
            box.prop(self.wf_props, "is_occluder")
            box.prop(self.wf_props, "is_sprite")
            box.separator()
            box.prop(self.wf_props, "in_stage_a")
            box.prop(self.wf_props, "in_stage_b")
            box.prop(self.wf_props, "in_stage_c")
            box.separator()
            box.prop(self.wf_props, "split")
            box.prop(self.wf_props, "light_mapped")
            box.prop(self.wf_props, "visible_to_raycast")
            box.prop(self.wf_props, "raycast_opaque")
            box.prop(self.wf_props, "raycast_transparent")
            box.separator()
            box.prop(self.wf_props, "bake_vertex_ao")
            box.prop(self.wf_props, "vertex_color")
            box.prop(self.wf_props, "track_objects_version")
            box.prop(self.wf_props, "trigger_group")

    @classmethod
    def poll(cls, context):
        poll_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if poll_meshes:
            return True
        return False

    def invoke(self, context, event):
        # self.reset_properties()
        return {'FINISHED'}

    def execute(self, context):
        # Reset all the properties
        for obj in bpy.context.view_layer.objects.selected:
            for prop in self.wf_props.items():
                self.toggle_property(obj, prop)

        return {'FINISHED'}

    def toggle_property(self, obj, enum_property):
        prop_name = self.wf_props.bl_rna.properties.get(enum_property[0]).name
        # If Unset
        if enum_property[1] == 1 and (("WF_" + prop_name) in obj.keys()):
            del obj["WF_" + prop_name]
        # else if True
        elif enum_property[1] == 2:
            obj["WF_" + prop_name] = True
        # else if False
        elif enum_property[1] == 3:
            obj["WF_" + prop_name] = False

    def reset_properties(self):
        items = self.wf_props.items()
        for prop in items:
            self.wf_props.property_unset(prop[0])
