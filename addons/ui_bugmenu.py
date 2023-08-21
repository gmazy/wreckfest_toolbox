# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons CC0
# https://creativecommons.org/publicdomain/zero/1.0/
#
# ##### END LICENSE BLOCK #####

bl_info = {  
    "name": "Bugmenu",  
    "author": "Mazay",  
    "version": (0, 1, 6),  
    "blender": (2, 80, 0),  
    "location": "Topbar",  
    "description": "Adds Bugmenu to topbar.",  
    "warning": "",  
    "wiki_url": "",  
    "tracker_url": "",  
    "category": "Interface"}  

bugmenu_copypaste = ''

import bpy
import os
import re
import sys
import subprocess
import bmesh
import mathutils
from bpy.props import StringProperty


class BUGMENU_MT_menu(bpy.types.Menu):
    bl_label = "Bugmenu"

    def op_exist(self,idname):
        op = bpy.ops
        for attr in idname.split("."):
            op = getattr(op, attr)
        return hasattr(bpy.types, op.idname())
    
    def draw(self, context):
        op_exist = self.op_exist
        layout = self.layout
        layout.scale_y = 1.3
        if op_exist("wftb.export_bgo"): layout.operator("wftb.export_bgo", text="Export BGO (Direct)", icon='EXPORT')
        if op_exist("wftb.export_bgo_with_dialog"): layout.operator("wftb.export_bgo_with_dialog", text="Export BGO (Set Path)", icon='EXPORT')
        bgo_text = "Export BGO"
        if op_exist("wftb.export_bgo"):
            layout.separator() 
            bgo_text += " (Old Exporter)"
        if op_exist("export_scene.bgo"): layout.operator("export_scene.bgo", text=bgo_text, icon='EXPORT')
        layout.separator()         
        if op_exist("import_scene.scne"): layout.operator("import_scene.scne", icon='IMPORT')
        if op_exist("import_scene.scneph"): layout.operator("import_scene.scneph", icon='IMPORT')
        layout.separator() 
        layout.operator("bugmenu.runbagedit")
        layout.separator() 
        layout.menu("BUGMENU_MT_repair")
        layout.separator()
        layout.menu("BUGMENU_MT_airoutes", icon='IPO_ELASTIC')
        layout.separator()
        layout.menu("BUGMENU_MT_set_shader", icon='NODE_MATERIAL')
        if (bpy.app.version>=(2,80)):
            layout.menu("BUGMENU_MT_set_material", icon='MATERIAL')
        layout.separator() 
        layout.operator("wm.call_menu", text="Set Custom Properties", icon='PRESET').name = "BUGMENU_MT_set_custom_properties"


class BUGMENU_MT_repair(bpy.types.Menu):
    bl_label = "Repair"
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.4
        layout.operator("bugmenu.repair_customdata", icon='LIBRARY_DATA_BROKEN')
        if (bpy.app.version>=(2,80)):
            layout.operator("bugmenu.update_customdata", icon='PRESET') 

class BUGMENU_MT_airoutes(bpy.types.Menu):
    bl_label = "Ai Routes"
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.4
        layout.operator("bugmenu.routes_from_curve", icon='GP_MULTIFRAME_EDITING')
        layout.operator("bugmenu.apply_modifier", icon='MODIFIER_ON')
   
class BUGMENU_MT_set_shader(bpy.types.Menu):
    bl_label = "Change Shader"
    def draw(self, context):
        layout = self.layout
        #layout.scale_y = 1.4
        layout.label(text="Set Shader for Blender view:")
        layout.separator()
        layout.label(text="Node Groups:", icon='NODETREE')
        for ng in reversed(bpy.data.node_groups):
            if '#export' in ng.name:
                text = ng.name.replace('#export','')
                layout.operator("bugmenu.set_shader", text=text).shader = ng.name
        layout.separator()
        layout.label(text="Blender Internal:", icon='NODE')
        layout.operator("bugmenu.set_shader", text='Principled BSDF').shader = 'Principled BSDF'
        layout.separator()
        layout.label(text="Append:", icon='APPEND_BLEND')
        if BUGMENU_MT_menu.op_exist(self,"wf_shaders.append_wf_shaders"): layout.operator("wf_shaders.append_wf_shaders")

class BUGMENU_MT_set_material(bpy.types.Menu):
    bl_label = "Set Material"
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.4
        layout.operator("bugmenu.setzerospec")
        
class BUGMENU_MT_set_custom_properties(bpy.types.Menu):
    bl_label = "Set CustomData:"
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2
        layout.operator("object.set_customdata", icon='NONE', text='Clear').value = 'Clear'
        layout.separator() 
        layout.label(text="Tracks / Objects:")
        layout.operator("object.set_customdata", text='col = true').value = 'col = true'
        layout.operator("object.set_customdata", text='vis = false').value = 'vis = false'
        layout.operator("object.set_customdata", text='col = true|vis = false').value = 'col = true|vis = false'
        layout.separator() 
        layout.label(text="Dynamic Type:")
        layout.operator("object.set_customdata", text='trafficcone').value = 'dyn = "data/property/object/trafficcone"'
        layout.operator("object.set_customdata", text='barrel').value = 'dyn = "data/property/object/barrel"'
        layout.operator("object.set_customdata", text='resetplayer').value = 'dyn = "data/property/object/resetplayer"'
        layout.operator("object.set_customdata", text='audio_start_area').value = 'dyn = "data/property/object/audio_start_area"'
        layout.operator("object.set_customdata", text='animtest').value = 'dyn = "data/property/object/animtest"'
        layout.operator("object.set_customdata", text='animation_colliding').value = 'dyn = "data/property/object/animation_colliding"'
        layout.operator("object.set_customdata", text='animation_colliding_random_start').value = 'dyn = "data/property/object/animation_colliding_random_start"'
        layout.operator("object.set_customdata", text='ghost').value = 'dyn = "data/property/object/ghost"'
        layout.separator() 
        layout.label(text="Volume Settings:")
        layout.operator("object.set_customdata", text='ambient_roaddust_gravel_01').value = 'vol = "data/property/object/ambient_roaddust_gravel_01"'   
        layout.separator() 
        layout.label(text="Routes:")
        layout.operator("object.set_customdata", text='otherway = true').value = 'otherway = true'
        layout.operator("object.set_customdata", text='crossstart = true').value = 'crossstart = true'
        layout.separator() 
        layout.label(text="Vehicles:")
        layout.operator("object.set_customdata", text='IsCollisionModel = true').value = 'IsCollisionModel = true'   
        layout.separator()
        layout.label(text="Copy-Paste:", icon='COPYDOWN')
        layout.operator("object.copy_customdata", text="Copy")
        if(bugmenu_copypaste != ''):
            layout.operator("object.set_customdata", text=bugmenu_copypaste).value = bugmenu_copypaste


# ------------------------------ Operators ------------------------------ #


class OBJECT_OT_set_customdata(bpy.types.Operator):
    """Sets Custom Property for Wreckfest (Object -> Custom Properties)"""
    bl_idname = "object.set_customdata"
    bl_label = "Set CustomData"
    bl_options = {'REGISTER', 'UNDO'}

    #value = StringProperty(default="x") #Blender 2.79
    value : StringProperty(default="x") #Blender 2.8+

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    @classmethod
    def description(cls, context, properties):
        descriptions = {
            'Clear':'Removes all Wreckfest custom properties',
            'col = true':'Enables collisions',
            'vis = false':'Turns object invisible. Visual model is no longer exported',
            'col = true|vis = false':'Invisible collision object. Used to create simplified collisions for static objects, fences etc.',
            'dyn = "data/property/object/trafficcone"':'Applies dynamics of traffic cone.',
            'dyn = "data/property/object/barrel"':'Applies dynamics of barrel',
            'dyn = "data/property/object/audio_start_area"':'Adds start area audio to object',
            'dyn = "data/property/object/animtest"':'Enables keyframe animations',
            'dyn = "data/property/object/animation_colliding"':'Enables colliding keyframe animations',
            'dyn = "data/property/object/animation_colliding_random_start"':'Enables colliding keyframe animations with random start time',
            'dyn = "data/property/object/ghost"':'Turns object invisible. Used in special cases for hiding placeholder object',
            'otherway = true':'Reverses Ai Route. Should be applied on #ai_route',
            'crossstart = true':'If the alt route crosses start/finish this property is needed. Apply on #ai_route.\nRemember to add also proxy checkpoint on alt route. (#checkpointXX_altX_proxy1)',
            'IsCollisionModel = true':'Turns object invisible. Used to hide vehicle collision spheres and proxies.',
        }
        text = properties.value
        if text in descriptions:
            text += '\n' + descriptions[text]
        text += "\n\nCustom properties will be added under Object -> Custom Properties"
        return text

    def execute(self, context):
        sel_objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        for obj in sel_objs:
            if(self.value=='Clear'): # Delete Custom Properties
                # Delete CustomData properties
                if(obj.get('CustomData') is not None): del obj['CustomData']
                # Delete WF_ properties
                for key in obj.keys(): 
                    if key.strip().startswith('WF_'): del obj[key] # Delete WF_ properties
            else:
                obj['CustomData'] = self.value
        if (bpy.app.version>=(2,80)): obj.select_set(state=True) #Refresh
        return {'FINISHED'}

class OBJECT_OT_copy_customdata(bpy.types.Operator):
    """Copy Wreckfest Custom Property"""
    bl_idname = "object.copy_customdata"
    bl_label = "Copy CustomData"

    @classmethod
    def poll(cls, context):
        return len(bpy.context.selected_objects) > 0 and bpy.context.selected_objects[0].get('CustomData') is not None

    def execute(self, context):
        global bugmenu_copypaste
        bugmenu_copypaste = bpy.context.selected_objects[0]['CustomData']
        return {'FINISHED'}

class BUGMENU_OT_runbagedit(bpy.types.Operator):
    """Run BagEdit from Wreckfest/BagEdit"""
    bl_idname = "bugmenu.runbagedit"
    bl_label = "BagEdit"

    @staticmethod
    def bagedit_path():
        return os.path.join(bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path,'BagEdit','BagEditCommunity.exe')

    @staticmethod
    def scene_path():
        try:
            path = bpy.context.scene.wftb_bgo_export_path
        except:
            return ''
        if os.path.isfile(path[:-5]+'.scne'):
            return path[:-5]+'.scne'
        if os.path.isfile(path[:-5]+'.vhcl'):
            return path[:-5]+'.vhcl'
        return ''

    @classmethod
    def poll(cls, context):
        try:
            if os.path.isfile(cls.bagedit_path()): return 1
        except:
            return 0

    def execute(self, context):
        scene_path = self.scene_path()
        args = [self.bagedit_path()]
        if sys.platform != 'win32':  args = ['wine'] + args
        if scene_path != '': args += [scene_path]
        subprocess.Popen(args)
        return {'FINISHED'}

class BUGMENU_OT_repair_customdata(bpy.types.Operator):
    """Repair for 3dsMax Fbx Imports: \n\n- Repair & Clean Custom Properties\n- Rename images with actual image name"""
    bl_idname = "bugmenu.repair_customdata"
    bl_label = "Repair Fbx import from 3dsMax"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        for obj in bpy.context.scene.objects:
            for key in obj.keys():
                if key == 'MaxHandle': return True
        return False

    def execute(self, context):
        customDataConversions = ['VisibleToRaycast', 'IsTestModel', 'IsWriteModel', 'IsOccluder', 'InVisual', 'InStageA', 'InStageB', 'InStageC', 'InCollision', 'IsSprite', 
    'IsCollisionModel', 'Split', 'LightMapped', 'VertexColors', 'RaycastOpaque', 'RaycastTransparent', 'vis', 'col', 'bakeVertexAO', 'TrackObjectsVersion', 'TriggerGroup', 'dyn']

        # Repair CustomData
        for obj in bpy.context.scene.objects: #
            for key in obj.keys():
                print(key)
                if key == 'MaxHandle' or key.startswith('mr displacement'): del obj[key]
                if key in customDataConversions: 
                    if 'CustomData' in obj:
                        obj['CustomData'] += '|'+key+' = '+str(obj[key]) # Add to CustomData field
                    else:
                        obj['CustomData'] = key+' = '+str(obj[key]) # New CustomData field
                    del obj[key] # Delete 3dsmax format

        # Rename images
        for img in bpy.data.images: 
            img.name = img.name.lstrip('Map ') # Remove Map from beginning
            filename = img.filepath.lstrip('//').split('\\')[-1]
            if(filename not in img.name): img.name = img.name+' '+filename # Add missing filename to name

        return {'FINISHED'}

class BUGMENU_OT_update_customdata(bpy.types.Operator):
    """Update Custom Properties to new WF_ format\n\nBefore: CustomData: col = true\nAfter:    WF_col: true\n\nApplies to selected objects."""
    bl_idname = "bugmenu.update_customdata"
    bl_label = "Update Custom Properties"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) > 0:
            for obj in bpy.context.selected_objects:
                for key in obj.keys():
                    if 'CustomData' in obj:
                        return True
        return False

    def execute(self, context):
        for obj in bpy.context.selected_objects: #
            for key in obj.keys():
                print(key)

                if 'CustomData' in obj:
                    customData = obj['CustomData']
                    del obj[key] # Delete old CustomData

                    lines = re.split('\r\n|\n|\r|\|', customData) # \r\n, \n, \r, |
                    for line in lines:
                        key,value = line.split('=',1)
                        key,value = key.strip(), value.strip()
                        if key != '' and value != '':
                            obj['WF_'+str(key)] = value

        if (bpy.app.version>=(2,80)): obj.select_set(state=True) #Refresh view
        return {'FINISHED'}

class BUGMENU_OT_airoutes_from_curve(bpy.types.Operator):
    """Generate Ai Routes From Curve  (Add > Curve > Path)
\nRoute:
    Scale to set width:    S
\nRoute in edit mode:
    Sector density:       A, S, X
\nEdit curve:
    Point width:          ALT + S
    Flatten:                 A, S, Z, 0, Enter """

    bl_idname = "bugmenu.routes_from_curve"
    bl_label = "1. Generate Ai Routes From Curve"
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator. Also prevents Undo crash in B 2.93

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type=='CURVE'

    def execute(self, context):
        def create_plane_mesh(name, size=0.5):
            bm = bmesh.new()
            mx = mathutils.Matrix.Scale(15, 4, (1, 0, 0)) #factor, size, axis = 15X Scale on axis X, applied to mesh.
            mx = mx @ mathutils.Matrix.Translation((0.5, 0, 0)) # Move pivot to edge
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size, matrix=mx)
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            bm.free()   
            return mesh   
        def create_plane_ob(mesh, name):
            ob = bpy.data.objects.new(name, mesh)
            bpy.context.scene.collection.objects.link( ob ) #add without collection
            bpy.context.view_layer.update()
            bpy.context.view_layer.objects.active = ob
            ob.select_set(True)
            return ob
        def create_route_ob(mesh, name, curve_ob, ob_color, color, colorname, existing_ob=''):
            plane_ob = create_plane_ob(mesh, name)
            plane_ob.show_all_edges = True
            plane_ob.show_wire = True
            plane_ob.color = ob_color
            if (colorname in bpy.data.materials):
                mat = bpy.data.materials.get(colorname)
            else:
                mat = bpy.data.materials.new(colorname)
            mat.diffuse_color = color
            #plane_ob.data.materials.append(None) # Add material slot
            plane_ob.active_material = mat # Add material slot
            plane_ob.material_slots[0].link = 'OBJECT' # Disable material sharing
            plane_ob.active_material = mat
            # Add array modifier
            array_mod = plane_ob.modifiers.new(name="Array", type='ARRAY')
            array_mod.fit_type = 'FIT_CURVE'
            array_mod.use_merge_vertices = True
            array_mod.curve = curve_ob
            curve_mod = plane_ob.modifiers.new(name="Curve", type='CURVE')
            curve_mod.object = curve_ob
            # Add constraints for easy editing
            loc_c = plane_ob.constraints.new('COPY_LOCATION')
            loc_c.target = curve_ob
            loc_c = plane_ob.constraints.new('COPY_ROTATION')
            loc_c.target = curve_ob
            c = plane_ob.constraints.new('LIMIT_SCALE')
            c.use_min_x, c.use_max_x, c.use_min_z, c.use_max_z = True, True, True, True
            c.min_x, c.max_x, c.min_z, c.max_z = 1, 1, 1, 1
            return plane_ob

        # Generate routes from existing curve    
        curve_ob = context.active_object
        if curve_ob.type=='CURVE':
            curve_ob.show_in_front = True # Show always in front
            curve_ob.data.twist_mode = 'Z_UP' # Route facing up

            route_ext = '_main'
            if 'alt' in curve_ob.name.lower(): # keep _alt1 in name
                route_ext = '_alt' + curve_ob.name.lower().split("alt")[-1]
                
            mesh = create_plane_mesh("ai_route"+route_ext) # Shared mesh
            route_ob = create_route_ob(mesh, '#ai_route'+route_ext, curve_ob, ob_color=(0,0,1, 1), color=(0, 0, 1, 0.10), colorname="blue-route")   
            route_ob.scale.y = 16
            safe_ob = create_route_ob(mesh, '#ai_safe'+route_ext, curve_ob, ob_color=(1,0,0, 1), color=(1, 0, 0, 0.15), colorname="red-route")  
            safe_ob.scale.y = 12
            race_ob = create_route_ob(mesh, '#ai_race'+route_ext, curve_ob, ob_color=(0,1,0, 1), color=(0, 0.8, 0.1, 1), colorname="green-route")
            race_ob.scale.y = 10
        return {'FINISHED'}

class BUGMENU_OT_apply_modifier(bpy.types.Operator):
    """Apply modifiers, constraints and transforms"""
    bl_idname = "bugmenu.apply_modifier"
    bl_label = "2. Apply Modifiers & Constraints"
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator. Also prevents Undo crash in B 2.93

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) > 0:
            for ob in context.selected_objects:
                if ob.name.startswith('#ai'): return True
        return False

    def execute(self, context):
        for selected in bpy.context.selected_objects:
            # Find objects sharing mesh
            shared_obs = []
            for ob in bpy.data.objects:
                if ob.data == selected.data and ob.type=='MESH' and ob.name.startswith('#ai'):
                    shared_obs.append(ob)
            for ob in shared_obs:
                # Apply modifiers
                ob.data = ob.data.copy() # Single user
                depsgraph = bpy.context.evaluated_depsgraph_get()
                bm = bmesh.new()
                bm.from_object(ob, depsgraph)
                bm.to_mesh(ob.data)
                bm.free()
                for modifier in ob.modifiers:
                    ob.modifiers.remove(modifier)
                    print(modifier)
                # Apply Constraints
                for c in ob.constraints:
                    if c.type=='LIMIT_SCALE':
                        ob.constraints.remove(c)
                        ob.scale.x=1
                        ob.scale.z=1
                    elif c.type=='COPY_ROTATION':
                        if c.target is not None:
                            ob.rotation_euler = c.target.rotation_euler
                        ob.constraints.remove(c)
                    elif c.type=='COPY_LOCATION':
                        if c.target is not None:
                            ob.location = c.target.location
                        ob.constraints.remove(c)
                # Apply Transform
                ob.data.transform(matrix=ob.matrix_basis) # Apply Transform to mesh
                ob.matrix_basis.identity() # Reset Transform
        return {'FINISHED'}

class BUGMENU_OT_set_shader(bpy.types.Operator):
    """Sets shader. This will affect only shading in Blender"""
    bl_idname = "bugmenu.set_shader"
    bl_label = "Set shader"
    bl_options = {'REGISTER', 'UNDO'}

    #shader = StringProperty(default='') #Blender 2.79
    shader : StringProperty(default='') #Blender 2.8+

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    @classmethod
    def description(cls, context, properties):
        descriptions = {
            'Load Shaders':'Add Wreckfest shaders into current file.',
        }
        shader = properties.shader
        text = 'Shader:\n' + shader
        if shader in descriptions:
            text += '\n' + descriptions[shader]
        return text

    def execute(self, context):
        if bpy.app.version >= (4,00):
            wf_bsdf_slots = {
            'Transmission Weight': 0, 
            'Base Color': 1,
            'Specular IOR Level': 2,
            'Specular Tint': 3,
            'Roughness': 4,
            'Emission Color': 5,
            'Alpha': 6,
            'Anisotropic': 7,
            'Normal': 8,
            'Coat Weight': 9,
            'IOR': 10,
            'Tangent': 11
            }
        else: # Blender 2.8-3.6
            wf_bsdf_slots = {
            'Transmission': 0, 
            'Base Color': 1,
            'Specular': 2,
            'Specular Tint': 3,
            'Roughness': 4,
            'Emission': 5,
            'Alpha': 6,
            'Anisotropic': 7,
            'Normal': 8,
            'Clearcoat': 9,
            'IOR': 10,
            'Tangent': 11
            }


        def capture_inputs(node):
            nodes_at_inputs = {} # Create dict of linked Nodes
            id = -1
            for ninput in node.inputs:
                id += 1
                if ninput.is_linked:
                    if node.type == 'BSDF_PRINCIPLED': # Reorder inputs, skip if not found
                        if ninput.name in wf_bsdf_slots:
                            nodes_at_inputs.update({wf_bsdf_slots[ninput.name]: ninput.links[0].from_socket}) # {Id: First node in socket}
                    else:
                        nodes_at_inputs.update({id: ninput.links[0].from_socket}) # {Id: First node in socket}
            return nodes_at_inputs

        def capture_output(node):
            if len(node.outputs) > 0 and node.outputs[0].is_linked:
                return node.outputs[0].links[0].to_socket
            return None

        def add_nodegroup_node(tree,linked_nodes,material):
            nd = tree.nodes.new("ShaderNodeGroup")
            nd.node_tree = bpy.data.node_groups[self.shader]
            max_input = len(nd.inputs)
            # Restore links to new node
            for node_id in linked_nodes:
                if node_id < max_input: # If input exists in new node
                    tree.links.new(nd.inputs[node_id], linked_nodes[node_id])
                    # Link alpha of texture in 2nd input to 14th alpha input of nodegroup
                    if node_id==1 and 13<=max_input and "Alpha" in nd.inputs[13].name:
                        image_node = linked_nodes[node_id].node
                        if image_node.type == 'TEX_IMAGE':
                            tree.links.new(nd.inputs[13], image_node.outputs['Alpha'])
                            # Fix viewport transparency
                            if material.blend_method=='OPAQUE' and image_node.image is not None:
                                path = image_node.image.filepath
                                if '_c1.' in path:
                                    material.blend_method = 'CLIP'
                                    material.shadow_method = 'CLIP'
                                elif '_c5.' in path:
                                    material.blend_method = 'HASHED'
                                    material.shadow_method = 'CLIP'
                                print('Set Alpha Clip for "'+material.name+'"')
            return nd

        def add_bsdf_node(tree,linked_nodes):
            nd = tree.nodes.new("ShaderNodeBsdfPrincipled")
            # Restore links to new node
            for node_id in linked_nodes:
                for bsdf_slot_name, value in wf_bsdf_slots.items():
                    if node_id == value: # If id found in slots
                        tree.links.new(nd.inputs[bsdf_slot_name], linked_nodes[node_id])
            return nd

        updated_node_trees = []
        for obj in bpy.context.selected_objects:
                #for slot in obj.material_slots:
                if len(obj.material_slots)>0: # Replace only active material
                    slot = obj.material_slots[obj.active_material_index] 
                    if slot.material and slot.material.node_tree and slot.material.node_tree.nodes: # Skip materials without nodes
                        print('Material "'+slot.material.name+'" shader replace')
                        tree = slot.material.node_tree
                        if tree not in updated_node_trees: # Skip already updated materials
                            updated_node_trees.append(tree)
                            for nd_name in tree.nodes.keys(): # Loop nodes. keys() copy to list to prevent infinite loop.
                                nd = tree.nodes[nd_name] 
                                if (nd.type == 'BSDF_PRINCIPLED' or nd.name == "Wreckfest Wrapper" or
                                    nd.type == 'GROUP' and ("#export" in nd.node_tree.name.lower() or "#export" in nd.label.lower())):
                                    # Capture node links and properties
                                    nodes_at_inputs = capture_inputs(nd)
                                    node_at_output = capture_output(nd)
                                    location = nd.location.x, nd.location.y
                                    width = nd.width
                                    # Remove node
                                    tree.nodes.remove(nd)
                                    # Create new node
                                    if self.shader == 'Principled BSDF': # If chosen menu option to Princibled BSDF
                                        new_node = add_bsdf_node(tree,nodes_at_inputs)
                                    else:
                                        new_node = add_nodegroup_node(tree,nodes_at_inputs,slot.material)
                                    # Restores links and properties
                                    new_node.location = location
                                    new_node.width = width
                                    if node_at_output and len(new_node.outputs)>0: tree.links.new(new_node.outputs[0], node_at_output)
        return {'FINISHED'}        

class BUGMENU_OT_setzerospec(bpy.types.Operator):
    """Add material to shader editor"""
    bl_idname = "bugmenu.setzerospec"
    bl_label = "default_zero_spec_s.tga  -  No Reflections"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        def image_refer(fileName, fullPath): #image loading for images that may not exist yet
            image = bpy.data.images.new(fileName, width=1, height=1) #new 1x1 px image
            image.source = 'FILE' #overwrite with external image
            image.filepath = fullPath
            image.generated_type ='UV_GRID'
            return image

        fileName = "default_zero_spec_s.tga"
        fullPath = r'//..\..\..\data\art\textures\default_zero_spec_s.tga'

        updated_node_trees = []
        for obj in bpy.context.selected_objects:
                for slot in obj.material_slots:
                    if slot.material is not None and slot.material.node_tree is not None and slot.material.node_tree.nodes is not None: # Skip materials without nodes
                        if "#blend" not in slot.material.name: # Skip materials with #blend
                            tree = slot.material.node_tree
                            if tree not in updated_node_trees: # Skip already updated materials
                                updated_node_trees.append(tree)
                                imageNode = tree.nodes.new('ShaderNodeTexImage')
                                imageNode.location = (-350,300+7*50*-1)
                                if fileName in bpy.data.images:
                                    imageNode.image = bpy.data.images.get(fileName)  #Use existing
                                else:
                                    imageNode.image = image_refer(fileName, fullPath=fullPath)  #Reference new image
                                
                                for nd in tree.nodes:
                                    if nd.type == 'BSDF_PRINCIPLED':
                                        coat_weight = 'Coat Weight' if bpy.app.version>=(4,00) else 'Clearcoat'
                                        tree.links.new(nd.inputs[coat_weight], imageNode.outputs['Color'])
                                    if (nd.name == "Wreckfest Wrapper" or
                                        nd.type == 'GROUP' and ("#export" in nd.node_tree.name.lower() or "#export" in nd.label.lower())):
                                        tree.links.new(nd.inputs[9], imageNode.outputs['Color'])
        return {'FINISHED'}




def draw_bugmenu(self, context):
    layout = self.layout
    layout.menu("BUGMENU_MT_menu")

classes = (
    BUGMENU_MT_menu,
    BUGMENU_MT_repair,
    BUGMENU_MT_airoutes,
    BUGMENU_MT_set_shader,
    BUGMENU_MT_set_material,
    BUGMENU_MT_set_custom_properties,
    OBJECT_OT_set_customdata,
    OBJECT_OT_copy_customdata,
    BUGMENU_OT_runbagedit,
    BUGMENU_OT_repair_customdata,
    BUGMENU_OT_update_customdata,
    BUGMENU_OT_airoutes_from_curve,
    BUGMENU_OT_apply_modifier,
    BUGMENU_OT_set_shader,
    BUGMENU_OT_setzerospec,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if (bpy.app.version>=(2,80)):
        bpy.types.TOPBAR_MT_editor_menus.append(draw_bugmenu)
        #bpy.types.VIEW3D_MT_object_context_menu.append(draw_bugmenu)
    else:
        bpy.types.INFO_HT_header.append(draw_bugmenu)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if (bpy.app.version>=(2,80)):
        bpy.types.TOPBAR_MT_editor_menus.remove(draw_bugmenu)
    else:
        bpy.types.INFO_HT_header.remove(draw_bugmenu)



if __name__ == "__main__":
    register()

    # The menu can also be called from scripts
    bpy.ops.wm.call_menu(name=BUGMENU_MT_menu.bl_idname)
