# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2016 Dummiesman
# Copyright (c) 2020 TheSpacebarRider, Mazay
#
# This software is released under the MIT License.
# http://opensource.org/licenses/MIT
#
# ##### END MIT LICENSE BLOCK #####

import os
import time
import struct
import subprocess
import sys
import bpy
import bmesh
import math
import mathutils
from bpy_extras.io_utils import ExportHelper


wf_custom_data = {
    "IsCollisionModel",
    "OtherWay",
}

wf_slots = {
    'ao_image': 0,
    'base_color_image': 1,
    'specular_color_image': 2,
    'specular_level_image': 3,
    'glossiness_image': 4,
    'self_illumination_image': 5,
    'opacity_image': 6,
    'filter_color_image': 7,
    'bump_image': 8,
    'mrs_image': 9,
    'refraction_image': 10,
    'displacement_image': 11
}
wf_bsdf_slots = {
    # Ambiant Oclusion
    'Transmission Weight': 0,
    'Transmission': 0, # Pre 4.0
    # Diffuse / Base Color
    'Base Color': 1,
    # Specular Color
    'Specular IOR Level': 2,
    'Specular': 2, # Pre 4.0
    # Specular Level
    'Specular Tint': 3,
    # Glossiness
    'Roughness': 4,
    # Self Illumination
    'Emission Color': 5,
    'Emission': 5, # Pre 4.0
    # Opacity
    'Alpha': 6,
    # Filter Color
    'Anisotropic': 7,
    # Bump
    'Normal': 8,
    # Reflection
    'Coat Weight': 9,
    'Clearcoat': 9, # Pre 4.0
    # Refraction
    'IOR': 10,
    # Displacement
    'Tangent': 11,
}

# Add a scene property to store the export path
bpy.types.Scene.wftb_bgo_export_path = bpy.props.StringProperty(
    name="BGO",
    subtype='FILE_PATH'
)


class WFTB_OP_export_bgo_with_dialog(bpy.types.Operator, ExportHelper):
    """Export the visible scene to a BGO File"""
    bl_idname = "wftb.export_bgo_with_dialog"
    bl_label = "Export"

    filename_ext = ".bgo3"

    filter_glob: bpy.props.StringProperty(
        default='*.bgo3',
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        context.scene["wftb_bgo_export_path"] = self.filepath

        bpy.ops.wftb.export_bgo()

        return {'FINISHED'}


class WFTB_OP_export_bgo(bpy.types.Operator):
    """Export the visible scene to a BGO File"""
    bl_idname = "wftb.export_bgo"
    bl_label = "Export"
    bl_description = "Export all the objects in the file excepted the ones placed in a collection with #exclude suffix"
    bl_options = {'BLOCKING'}

    prefs = None

    def __init__(self):
        # Get if the scene have a custom property referencing the export path
        self.export_path = bpy.context.scene.get('wftb_bgo_export_path')
        self.output = None
        self.errors = None
        self.done_bmaps = [] 

    def execute(self, context):
        """The exporter will export every objects,
         as long as they are not part of any collection that have the suffix #exclude"""
        self.prefs = bpy.context.preferences.addons["wreckfest_toolbox"].preferences

        if not self.export_path:
            return {'CANCELLED'}

        print("----------------------------------------")
        print('exporting BGO: %r...' % self.export_path)

        # Force object mode
        try: # To avoid issues when context or active object is missing
            bpy.ops.object.mode_set(mode='OBJECT')
        except: pass

        time1 = time.time()
        wm = bpy.context.window_manager
        total = 100
        wm.progress_begin(0, total)
        with open(self.export_path, 'wb') as file:
            file.write(struct.pack('I', 0)) # File length
            file.write(bytes('MAIN', 'utf-8'))
            print("Write Info ...")
            self.write_info(file)
            print("Write Materials ...")
            self.write_materials(file)
            print("Write Objects ...")
            self.write_objects(file)
            self.write_filelen(0, file) # Rewrite file length at the beginning

        self.show_message('export done in %.4f sec.' % (time.time() - time1))
        print("----------------------------------------")
        if self.prefs.build_after_export:
            self.build_and_notify()

        return {'FINISHED'}

    def show_message(self, message="", message_type='INFO'):
        def draw(self, context):
            self.layout.label(text=message)

        bpy.context.window_manager.popup_menu(draw, title='BGO Exporter', icon=message_type)
        print(message_type, " : ", message)

    @staticmethod
    def object_has_pivot(ob):
        for cs in ob.constraints:
            if cs.type == 'PIVOT':
                return cs

    @staticmethod
    def flip_axes(ob):
        new_rot = (
            ob.rotation_euler[0] * -1, ob.rotation_euler[2] * -1, ob.rotation_euler[1] * -1)
        ob.rotation_euler = mathutils.Vector(new_rot)
        new_scl = (
            ob.scale[0], ob.scale[2], ob.scale[1])
        ob.scale = mathutils.Vector(new_scl)
        bpy.context.view_layer.update()

    @staticmethod
    def get_relative_texpath(absolute_path):
        splts = absolute_path.replace('\\', '/').lower().split('/')
        relative_path = None
        if 'data' in splts:
            relative_path = ('/').join(splts[splts.index('data'):])
        return relative_path

    @staticmethod
    def reorder_objects(lst, pred):
        return_list = [
                          None] * len(pred)
        for v in lst:
            try:
                return_list[pred.index(v.name)] = v
            except:
                return_list.append(v)

        return [x for x in return_list if x is not None]

    @staticmethod
    def create_blank_matrix():
        mat_loc = mathutils.Matrix.Translation((0.0, 0.0, 0.0))
        mat_sca = mathutils.Matrix.Scale(1, 4, (1.0, 1.0, 1.0))
        mat_rot = mathutils.Matrix.Rotation(0, 4, 'X')
        # Deprecated : return mat_loc * mat_rot * mat_sca
        # https://blender.stackexchange.com/questions/129473/typeerror-element-wise-multiplication-not-supported-between-matrix-and-vect
        return mat_loc @ mat_rot @ mat_sca

    @staticmethod
    def get_material_id_list(obj):
        # Create dict of all scene material names and indices, {"Name": id}
        scene_mat_id = {mat.name: i for i, mat in enumerate(bpy.data.materials)}
        # Create list of all object's material id (global id)
        indices = []
        for mat in obj.data.materials:
            if mat is not None:
                indices += float(scene_mat_id[mat.name]),
            else: # Empty material slots reset to 0
                indices += float(0),
        return indices

    @staticmethod
    def get_exportables():
        """Get all the objects in the scene"""
        exportables = []
        # get objects in visible collections
        for obj in bpy.context.view_layer.objects:
            if (obj.type == 'MESH' or obj.type == 'EMPTY') and ('PivotObject' not in obj) and (obj.hide_viewport == False):
                is_exportable = True
                for collection in obj.users_collection:
                    if collection.name.endswith("#exclude"):
                        is_exportable = False
                if is_exportable:
                    exportables.append(obj)

        return exportables

    @staticmethod
    def get_undupe_name(name):
        nidx = name.rfind('.')
        if nidx != -1:
            return name[:nidx]
        return name

    @staticmethod
    def write_matrix(matrix, file, sub_vector=None):
        m2 = matrix.transposed()
        lx = matrix[0][3]
        ly = matrix[2][3]
        lz = matrix[1][3]
        if sub_vector is not None:
            lx -= sub_vector[0]
            ly -= sub_vector[2]
            lz -= sub_vector[1]
        file.write(struct.pack('ffff', matrix[0][0], matrix[1][0], matrix[2][0], matrix[3][0]))
        file.write(struct.pack('ffff', matrix[0][1], matrix[1][1], matrix[2][1], matrix[3][1]))
        file.write(struct.pack('ffff', matrix[0][2], matrix[1][2], matrix[2][2], matrix[3][2]))
        file.write(struct.pack('ffff', lx, ly, lz, matrix[3][3]))

    @staticmethod
    def write_flipped_matrix(matrix, file):  # Matrix with Y and Z swapped
        file.write(struct.pack('ffff', matrix[0][0], matrix[2][0], matrix[1][0], matrix[3][0]))
        file.write(struct.pack('ffff', matrix[0][2], matrix[2][2], matrix[1][2], matrix[3][2]))
        file.write(struct.pack('ffff', matrix[0][1], matrix[2][1], matrix[1][1], matrix[3][1]))
        file.write(struct.pack('ffff', matrix[0][3], matrix[2][3], matrix[1][3], matrix[3][3]))

    @staticmethod
    def write_filelen(offset, file, additional_adding=0):
        final_filelen = file.tell() - offset + additional_adding
        file.seek(offset)
        file.write(struct.pack('I', final_filelen))
        file.seek(0, 2)
        return final_filelen

    @staticmethod
    def write_cstring(string, file):
        file.write(bytes(string + '\x00', 'utf-8'))

    @staticmethod
    def write_color3f(color, file):
        file.write(struct.pack('fff', color[0], color[1], color[2]))

    @staticmethod
    def create_header(header_name, header_size, file):
        file.write(struct.pack('I', header_size))
        file.write(bytes(header_name, 'utf-8'))
        return file.tell() - 8

    def write_info(self, file):
        info_start_offset = self.create_header('INFO', 0, file)
        file.write(struct.pack('I', 777))
        self.write_cstring('BGO', file)
        my_username = os.environ['USERNAME'] if 'USERNAME' in os.environ else 'UNKNOWN_USERNAME'
        self.write_cstring(my_username, file)
        self.write_filelen(info_start_offset, file)

    def write_materials(self, file):
        mlst_start_offset = self.create_header('MLST', 0, file)
        file.write(struct.pack('I', len(bpy.data.materials)))
        for mtl in bpy.data.materials:
            self.write_material_individual(mtl, file)

        self.write_filelen(mlst_start_offset, file)

    def write_material_individual(self, mat, file):
        """Write a material in the file"""
        matc_start_offset = self.create_header('MATC', 0, file)
        file.write(bytes('\x00' * 32, 'utf-8'))
        self.write_color3f(mat.diffuse_color, file)
        self.write_color3f(mat.diffuse_color, file)
        self.write_color3f(mat.specular_color, file)
        file.write(struct.pack('f', mat.roughness))
        file.write(struct.pack('f', mat.specular_intensity))
        mat_alpha = 1
        if mat.diffuse_color[3] < 1:
            mat_alpha = mat.diffuse_color[3]  # hopefully fixed right
            # mat_alpha -= mat.alpha # crashes
        file.write(struct.pack('f', mat_alpha))
        file.write(struct.pack('I', 2))
        file.write(bytes('\x00\x00\x00\x00', 'utf-8'))
        file.write(struct.pack('I', 0))
        file.write(bytes('\x00\x00\x00\x00', 'utf-8'))
        self.write_cstring(mat.name, file)

        is_material_written = False
        if mat.node_tree is not None:
            # Find the wreckfest node
            for nd in mat.node_tree.nodes:
                if nd.name == 'Wreckfest Wrapper':
                    self.write_wreckfest_wrapper_node(nd, file)
                    is_material_written = True
                    break
            # if no wreckfest node found, look for node group with # in title.
            if not is_material_written:
                for nd in mat.node_tree.nodes:
                    if nd.type == 'GROUP' and nd.node_tree is not None: 
                        if "#" in nd.node_tree.name.lower() or "#" in nd.label.lower(): # Label or Name
                            self.write_nodegroup_node(nd, mat, file)
                            is_material_written = True
                            break
            # at last look for principled_bsdf
            if not is_material_written:
                for nd in mat.node_tree.nodes:
                    if nd.type == 'BSDF_PRINCIPLED':
                        self.write_bsdf_node(nd, mat, file)
                        is_material_written = True
                        break
        # if no wreckfest node was found just close the material struct
        if not is_material_written:
            # print("No correct nodes found in material : " + mat.name)
            file.write(struct.pack('I', 0))

        self.write_filelen(matc_start_offset, file)

    def write_wreckfest_wrapper_node(self, node, file):
        """For each WF slot, look if a texture was registered, if yes, write it"""
        texture_paths = {}
        for key in wf_slots:
            image = node.get(key)
            if type(image) is bpy.types.Image:
                texture_paths[wf_slots[key]] = image.filepath

        file.write(struct.pack('I', len(texture_paths)))

        for slot in texture_paths:
            self.write_texture_individual(node, slot, texture_paths[slot], file)

    def write_bsdf_node(self, node, mat, file):
        # Create a dictionary of linked TEX_IMAGE Node (Shader input : TEX_Node)
        tex_nodes = {}

        # Go through shader node inputs
        for sh_in in node.inputs:
            if sh_in.is_linked:
                # WARNING : This can skip texture if people link smtg else than a TEX_IMAGE and/or link multiple things
                if sh_in.links[0].from_socket.node.type == 'TEX_IMAGE':
                    tex_nodes[sh_in.name] = sh_in.links[0].from_socket.node

        # Just take the len of linked Tex Nodes
        file.write(struct.pack('I', len(tex_nodes)))

        # Go through registered texture nodes with their link
        for tn in tex_nodes:
            try:
                self.write_texture_node_individual(tex_nodes[tn], wf_bsdf_slots[tn], file)
            except KeyError:
                self.show_message(
                    'Texture in incorrect slot "' + tn + '" in material: "' + mat.name + '"',
                    'ERROR')
                self.write_texture_node_individual(tex_nodes[tn], 1, file)  # default to slot 1

    def write_nodegroup_node(self, node, mat, file):
        # Create a list of linked TEX_IMAGE Node
        tex_nodes = []

        # Go through nodegroup node inputs
        node_id = -1
        for sh_in in node.inputs:
            node_id += 1
            # WARNING : This can skip texture if people link smtg else than a TEX_IMAGE and/or link multiple things
            if node_id < 12 and sh_in.is_linked and sh_in.links[0].from_socket.node.type == 'TEX_IMAGE':
                tn = {}
                tn["node"] = sh_in.links[0].from_socket.node
                tn["id"] = node_id
                tex_nodes += (tn),

        # Write len of linked Tex Nodes
        file.write(struct.pack('I', len(tex_nodes)))

        # Go through valid texture nodes with their link
        for tn in tex_nodes:
            self.write_texture_node_individual(tn["node"], tn["id"], file)

    def build_bmap_file(self,filepath):
        '''Convert .tga, .png texture to .bmap with bgeometry.exe'''
        filepath = filepath.replace('\\', '/') # To linux paths
        if filepath[-4:].lower() in ['.png','.tga'] and filepath not in self.done_bmaps: 
            self.done_bmaps.append(filepath)  # Progress each file only once.
            if '/data/' in filepath: # Check that file is under /data/ folder
                bmap_filepath = filepath[:-4] + '.bmap'
                try: tga_lastmodified = os.path.getmtime(filepath) # Check that .tga file exists, get last modified time
                except: return  # .tga file does not exist
                try: bmap_lastmodified = os.path.getmtime(bmap_filepath) # Try check .bmap last modified time
                except: bmap_lastmodified = 0  # .bmap file does not exist
                if tga_lastmodified > bmap_lastmodified: # Check that .tga is more recent than .bmap
                    relative_path = '/data/' + bmap_filepath.rsplit('/data/',maxsplit=1)[-1]
                    if not os.path.isfile(self.prefs.wf_path + relative_path): # Check that matching name .bmap does not exist in wreckfest install.
                        print(os.path.basename(filepath),"conversion to .bmap with bimage.exe ...")
                        bimage = self.prefs.wf_path + R"\tools\bimage.exe"
                        args = [bimage, '-auto', '-input', filepath, '-output', bmap_filepath]
                        if sys.platform != 'win32':  args = ['wine'] + args # In Linux run .exe with wine
                        try: subprocess.Popen(args) # Run bimage in background
                        except: print("Failed to run bimage.exe")

                        # Try build alternative textures
                        if '/vehicle/' in filepath and filepath.lower()[-7:-3] == '_c5.':
                            for ext in 'c5','n','s','ao_c','damaged_c5','damaged_n','damaged_s':
                                self.build_bmap_file(filepath[:-6] + ext + filepath[-4:])

    # This method take a  TEX Node in param, and it's slot_id from Princ BSDF to WF dict
    def write_texture_node_individual(self, node, slotid, file):
        texture_path = None
        if node.image is not None and node.image.filepath is not None:
            # Get the image Path
            texture_path = node.image.filepath
        self.write_texture_individual(node, slotid, texture_path, file)

    def write_texture_individual(self, node, slotid, texture_path, file):
        if texture_path is not None:
            # Convert Blender relative paths to Wreckrest relative paths
            absolute_texture_path = os.path.abspath(bpy.path.abspath(texture_path))
            texture_path = self.get_relative_texpath(absolute_texture_path)
        # If relative path solve was success
        if texture_path is not None:
            # Convert .tga to .bmap
            if self.prefs.build_bmap:
                self.build_bmap_file(absolute_texture_path)
            # Rename unsupported formats to bypass build_asset checks. PNG should be removed once it's officially supported.
            if texture_path[-4:].lower() in ['.png','.jpg']: 
                texture_path = texture_path[:-4] + '.tga'
        else:
            # Use default fallback texture when file is outside of /data/
            texture_path = 'data/art/textures/tmp_red_c.tga'

        uvid = 1
        scale_x = 1
        scale_y = 1
        # Go through nodes at Vector input of Image node
        node_input = node.inputs['Vector']
        if node_input.is_linked:
            # Get material scale from Mapping node
            linked_node = node_input.links[0].from_socket.node
            ntype = linked_node.type
            if ntype=='MAPPING': # Mapping node
                scale_x, scale_y, _ = linked_node.inputs['Scale'].default_value
            elif ntype=='GROUP': # Nodegroup with Scale
                if 'Scale' in linked_node.inputs and linked_node.inputs['Scale'].type=='VECTOR':
                    scale_x, scale_y, _ = linked_node.inputs['Scale'].default_value
            # Find UV node
            if ntype=='MAPPING' or ntype=='GROUP':
                inputs = linked_node.inputs
                if len(inputs)>0 and inputs[0].is_linked:
                    linked_node = inputs[0].links[0].from_socket.node
            # Change UV for #blend, Triggered by name 'UVMap2' as UVs don't have order.
            if linked_node.type=='UVMAP' and linked_node.uv_map.lower()=='uvmap2':
                uvid = 2

        texc_start_offset = self.create_header('TEXC', 0, file)
        file.write(struct.pack('III', slotid, uvid, 0)) # Material id, Misc param 0, ?
        # 4x4 Inverse transfrom matrix, Z-up
        # Used store #blend tiling factor for Misc param 1-2
        file.write(struct.pack('ffff', scale_x, 0, 0, 0))
        file.write(struct.pack('ffff', 0, scale_y, 0, 0))
        file.write(struct.pack('ffff', 0, 0, 1, 0))
        file.write(struct.pack('ffff', 0, 0, 0, 1))
        self.write_cstring(texture_path, file)
        self.write_filelen(texc_start_offset, file)

    def write_gmesh(self, ob, file):
        ob_material_id_list = self.get_material_id_list(ob)
        # print('writing mesh for ' + ob.name)
        gmesh_start_offset = self.create_header('GMSH', 0, file)
        bm = bmesh.new()
        # TODO : See to_mesh to use preserve all data layer
        # temp_mesh = ob.to_mesh()
        # bm.from_mesh(temp_mesh)
        # TODO: Apply modifiers based on: self.prefs.apply_modifiers
        depsgraph = bpy.context.view_layer.depsgraph
        bm.from_object(object=ob, depsgraph=depsgraph) 

        bm_tris = bm.calc_loop_triangles()
        uv_layers = len(bm.loops.layers.uv)
        range_uv_layers = range(uv_layers) # Range outside of loop, faster
        file.write(struct.pack('II', len(bm_tris), uv_layers))
        for tri in bm_tris:
            mat_index = 0
            try:
                mat_index = ob_material_id_list[tri[0].face.material_index] # Local material id to scene material id
            except Exception:
                mat_index = 0

            for loop in tri[::-1]:
                vco = loop.vert.co
                file.write(struct.pack('ffff', mat_index, vco[0], vco[2], vco[1]))
                for uvl in range_uv_layers:
                    normal = loop.vert.normal # Access bpy once, faster
                    uv_data = loop[bm.loops.layers.uv[uvl]].uv
                    c1p = normal.cross(mathutils.Vector((0.0, 0.0, 1.0)))
                    c2p = normal.cross(mathutils.Vector((0.0, 1.0, 0.0)))
                    loop_tang = c2p
                    if c1p.length > c2p.length:
                        loop_tang = c1p
                    loop_binormal = normal.cross(loop_tang)
                    file.write(struct.pack('fffffffffff',  # combining struck.pack is faster
                                           uv_data[0], ((uv_data[1] - 1) * -1),
                                           normal[0], normal[2], normal[1],
                                           loop_tang[0], loop_tang[2], loop_tang[1],
                                           loop_binormal[0], loop_binormal[2], loop_binormal[1]))

        # bpy.data.meshes.remove(temp_mesh) No longer needed
        bm.free()
        self.write_filelen(gmesh_start_offset, file, -8)

    @staticmethod
    def get_keyframes(obj): # Get every keyframe. Subframes return as decimals.
        keyframes = []
        if obj.animation_data is not None and obj.animation_data.action is not None:
            for fcu in obj.animation_data.action.fcurves:
                for keyframe in fcu.keyframe_points:
                    keyframes.append(keyframe.co.x) #co.x = time
        return sorted(set(keyframes)) #remove doubles and order

    @staticmethod
    def write_animations(self, file, exportables, objects_id_dictionary, bake_animation=False):
        second = 4800 # length of second (3dsMax internal unit)
        fps = round(bpy.context.scene.render.fps / bpy.context.scene.render.fps_base)
        firstFrameTime = round(bpy.context.scene.frame_start / fps * second)
        lastFrameTime = round(bpy.context.scene.frame_end / fps * second)

        # Write animation Info header
        anfo_offset = self.create_header('ANFO', 0, file)
        file.write(struct.pack('5I', second, firstFrameTime, fps, 0, lastFrameTime)) 
        file.write(struct.pack('8I', 0, 0, 0, 0, 0, 0, 0, 0))

        frame_before = bpy.context.scene.frame_current #backup frame selection
        for obj in exportables:
            if obj.animation_data is not None and obj.animation_data.action is not None:
                if self.find_object_type(obj) == 'OBJM':    
                    anim_offset = self.create_header('ANIM', 0, file)
                    file.write(struct.pack('I', objects_id_dictionary[obj.name])) #Object ID (reference to mesh)
                    asmp_offset = self.create_header('ASMP', 0, file)

                    keys = self.get_keyframes(obj) # Get every keyframe number
                    
                    if(bake_animation): # 1 Keyframe every Blender frame
                        firstFrame = round(keys[0])
                        lastFrame = round(keys[-1])
                        file.write(struct.pack('I', lastFrame-firstFrame+1)) #Number of keyframes
                        for frame in range(firstFrame, lastFrame+1):
                            bpy.context.scene.frame_set(frame) #move to frame
                            wfTime = round((frame - bpy.context.scene.frame_start) / fps * second) #time
                            if(wfTime<0): wfTime = 0 # bugfix for frames before frame_start
                            file.write(struct.pack('I', wfTime)) 
                            self.write_flipped_matrix(obj.matrix_local, file) #transform matrix
                    else: # Original keyframe data
                        file.write(struct.pack('I', len(keys))) #Number of keyframes
                        for frame in keys:
                            bpy.context.scene.frame_set(frame=math.floor(frame), subframe=frame%1) #move to frame
                            wfTime = round((frame - bpy.context.scene.frame_start) / fps * second) #time
                            if(wfTime<0): wfTime = 0 # bugfix for frames before frame_start
                            file.write(struct.pack('I', wfTime)) 
                            self.write_flipped_matrix(obj.matrix_local, file) #transform matrix

                    self.write_filelen(asmp_offset, file, 0)
                    self.write_filelen(anim_offset, file, 0)
        self.write_filelen(anfo_offset, file, 0)
        bpy.context.scene.frame_set(frame_before) #restore original frame selection

    @staticmethod
    def find_xref_path(obname, exporting_to_path=""):  # Find xref path from object name
        name = obname.replace('\\', '/')
        name = name.replace("#xref", "")
        name = name.replace(" ", "")
        name = name.rstrip('1234567890.')  # remove .001 from end
        # replace ob/ and le/ shorts
        if name[:3].lower() == "ob/": name = "data/art/objects/" + name[3:]
        if name[:3].lower() == "le/": name = "data/art/levels/" + name[3:]
        if name[:2].lower() == "//": name = exporting_to_path + name[2:]
        return name

    @staticmethod
    def fake_xref_name(name):  # fake 3dsmax style name
        name = name.replace('\\', '/').split("/")[-1]
        name = name.replace(".scne.", "#xref")
        name = name.replace(".scne", "#xref")
        return name

    @staticmethod
    def get_custom_data(obj):
        custom_data = ""
        if 'CustomData' in obj:
            custom_data = obj['CustomData'] + "\r\n"

        for key, value in obj.items():
            if key.startswith("WF_"):
                if value in [1, '1', 'true']: # Boolean is int, Manually typed value is sometimes string.
                    prop_value = "true"
                elif value in [0, '0', 'false']:
                    prop_value = "false"
                else: # Other text values
                    prop_value = '"' + str(value).strip('"') + '"'
                custom_data += key[3:] + " = " + prop_value + "\r\n"

        return custom_data

    @staticmethod
    def find_object_type(ob):
        # OBJX = Subscene: Object with #xref in name (unofficial) or Object with linked library (File > link)
        if ob.name.strip().startswith("#xref") or (ob.data is not None and ob.data.library is not None):
            return 'OBJX'
        if ob.type == 'MESH':
            return 'OBJM'
        if ob.type == 'EMPTY':
            return 'OBJD'
        return ''

    def write_objects(self, file):
        """Get all the objects that are not in a collection with the suffix #exclude"""
        hier_start_offset = self.create_header('HIER', 0, file)
        exportables = self.get_exportables()
        file.write(struct.pack('I', len(exportables)))
        objects_id_dictionary = {}
        objects_id_current = 1
        objects_id_mesh = -1
        for obj in exportables:
            #print('writing object ' + obj.name)
            object_type = self.find_object_type(obj)
            if object_type == '':
                continue
            if object_type == 'OBJM':
                objects_id_mesh += 1

            objects_id_dictionary[obj.name] = objects_id_current
            object_offset = self.create_header(object_type, 0, file)
            if obj.parent is not None:
                file.write(struct.pack('I', objects_id_dictionary[obj.parent.name]))
            else:
                file.write(struct.pack('I', 0))
            file.write(struct.pack('I', 0))

            pivot = self.object_has_pivot(obj)
            if pivot is not None:  # If special pivot constraint used?
                self.flip_axes(obj)  # slow
                self.write_matrix(obj.matrix_local, file)
                # print('using pivot matrix from ' + pivot.target.name + ' for ' + obj.name)
                self.flip_axes(pivot.target)
                self.write_matrix(pivot.target.matrix_local, file, obj.location)
                self.flip_axes(pivot.target)
                self.flip_axes(obj)
            else:  # normal model
                self.write_flipped_matrix(obj.matrix_local, file)
                self.write_matrix(self.create_blank_matrix(), file)

            file.write(struct.pack('II', 0, 3))
            if obj.name.strip().startswith("#xref"):  # Rewriting names of Xref Subscene
                self.write_cstring(self.fake_xref_name(obj.name), file)
            else:
                self.write_cstring(obj.name, file)

            # Write custom data

            customdata = self.get_custom_data(obj)

            self.write_cstring(str(customdata).replace('|', '\r\n'), file)
            if object_type == 'OBJM':
                file.write(struct.pack('I', objects_id_mesh))
                self.write_gmesh(obj, file)
            if object_type == 'OBJX':
                if obj.name.strip().startswith("#xref"): # Xref Subscene (Unofficial)
                    self.write_cstring(self.find_xref_path(obj.name)[:-5] + '.scn', file)
                else:  # File > link Subscene
                    apth = os.path.abspath(bpy.path.abspath(obj.data.library.filepath))
                    self.write_cstring(str(self.get_relative_texpath(apth.replace(".blend", ".ble"))), file)
            objects_id_current += 1

            self.write_filelen(object_offset, file, -8)
            self.write_filelen(hier_start_offset, file, -8)

        self.write_animations(self, file, exportables, objects_id_dictionary, self.prefs.bake_animation)


    def build_and_notify(self):
        bgeometry = os.path.join(self.prefs.wf_path, 'tools', 'bgeometry.exe') # os independent path
        export_path = self.export_path
        if '/vehicle/' in export_path or '\\vehicle\\' in export_path:
            popen_args = [bgeometry, '-v', '-vhcl', '-input', export_path, '-output', export_path[:-5]+'.vhcl']
        else:
            popen_args = [bgeometry, '-v', '-input', export_path, '-output', export_path[:-5]+'.scne']
        if sys.platform != 'win32': # In Linux run with wine
            popen_args = ['wine'] + popen_args
        if os.path.isfile(bgeometry):
            print("Building asset ...")
            thread = self.prefs.popen_and_call(self.notify, popen_args)

    def notify(self):
        print("... Building Done")

