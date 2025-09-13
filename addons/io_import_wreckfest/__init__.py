# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons CC0
# https://creativecommons.org/publicdomain/zero/1.0/
#
# ##### END LICENSE BLOCK #####


# Credits: 
# - Thanks to Cartoons for collision shape import

bl_info = {  
    "name": "Import Bugbear SCNE format (.scne/.vhcl/.vhcm)",  
    "author": "Mazay, Cartoons",  
    "version": (1, 0, 5),  
    "blender": (2, 80, 0),  
    "location": "File > Import",  
    "description": "Imports Wreckfest SCNE, VHCL and VHCM files",  
    "warning": "",  
    "wiki_url": "",  
    "tracker_url": "",  
    "category": "Import-Export"}

class config():
    # Bmap Cache Configuration
    c_resolution = 1500 # Cache image maximum resolution, 1024, 2048 etc.
    c_extension = 'cmap' # Cache image extension, 'cmap' or 'webp'

    # Command to run Wine
    wine_cmd = 'wine'

import bpy
import os
import binascii
import struct
import subprocess, sys
import re
import random
import bmesh
import mathutils
import hashlib
import time
import math
import tempfile
import addon_utils
import numpy as np
from .bagparse import BagParse

try:
    from . import uv
except ImportError:
    pass

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty
from bpy.types import Operator, AddonPreferences

class io_import_wreckfest(AddonPreferences):
    '''Addon preferences when addon installed separately'''
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    breckfestPath : StringProperty(
            name="Breckfest.exe",
            description="\nLocate Breckfest.exe to be able to import files",
            subtype='FILE_PATH',
            default=r"C:\Program Files (x86)\Steam\SteamApps\common\Wreckfest\tools\Breckfest.exe",
            )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "breckfestPath")
  
# ------------------------------ Operators ------------------------------ #      

class ImportScneData(bpy.types.Operator, ImportHelper):
    '''Imports Wreckfest SCNE or VHCL file'''
    bl_idname = "import_scene.scne"  # this is important since its how bpy.ops.import.some_data is constructed
    bl_label = "Import SCNE"
    bl_options = {"UNDO"}

    # ExportHelper mixin class uses this
    filename_ext = ".scne"

    filter_glob : StringProperty(default="*.scne;*.scne.raw;*.vhcl;*.vhcm", options={'HIDDEN'})  
    
    # Selected files
    directory: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    files : bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE'})

    # List of operator properties
    short_pth : BoolProperty(name="Short paths", description="Use shorthand paths with subscene placeholders\n\nReplaces data/art/objects with ob/", default=True) 
    use_color : BoolProperty(name="Use colors", description="Use semi-random colors with subscene placeholders", default=True)
    imp_mat : BoolProperty(name="Materials  (No UV)", description="Import Materials\n\nIMPORTANT:\nSave .blend file before importing under folder mods/xxx/data/... to ensure relative paths work correctly\n\nNote:\n- No UV mapping, textures will not show on models", default=True)
    imp_tga : BoolProperty(name="Materials: Save .tga textures to disk", description="Convert .bmap into .tga texture and save to disk\n\nIMPORTANT:\n- Save .blend file on disk beforehand under mods/xxx/data/...\n\nNote:\n- Only base color texture in low quality\n- Will recreate all material folders in their relative locations under current data folder", default=False)
    imp_model : BoolProperty(name="Models", description="Import Models\n\nNote:\n- Partial import\n- No UV mapping\n- High quality models including #lod1 ignored\n- Collision only models import as cubes", default=True)
    imp_shpe : BoolProperty(name="Models-collision", description="Import Models collision shape\n\nNote:\n- Work in progress. Does not have correct transform", default=False)
    imp_anim : BoolProperty(name="Animations", description="Import Animations\n\nNote:\n- Slow imports\n- You may want to set scene frame rate before importing animations", default=True)
    imp_subscn : BoolProperty(name="Subscenes", description="Import Subscene Placeholders\n\nNote:\n- Imports using unofficial specification.\n- Ignored: Name, Heading, Flags:Start", default=True)
    imp_subscn_mdl : BoolProperty(name="Subscenes: Import placeholder", description="Imports all linked subscene files.\n\n- Generates simplified placeholder of each model\n- Turn this off if import fails", default=True)
    imp_portal : BoolProperty(name="Antiportals", description="Import Antiportals\n\nNote:\n- Work in progress\n- Does not export properly as bounding box is not following geometry", default=True)
    imp_airt : BoolProperty(name="Airoutes", description="Import Airoutes", default=True)
    imp_startpt : BoolProperty(name="Startpoints", description="Import Startpoints", default=True)
    imp_cp : BoolProperty(name="Checkpoints", description="Import Checkpoints\n\nNote:\n- Checkpoint height is arbitary value", default=True)
    imp_vol : BoolProperty(name="Trigger Volumes", description="Import Trigger Volumes", default=True)
    imp_pfb : BoolProperty(name="Prefabs", description="Import Prefabs", default=True)
    use_wftb : BoolProperty(name="Use WFTB Shaders", description="Use Wreckfest Modding Toolbox Shaders\n\n- Materials with Bugmenu shaders", default=True)
    debug : BoolProperty(name="Debug", description="Import debug models\n\n- Ai route sector numbering\n- Vehicle Deform data", default=False)

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob','filepath','files')) # Include operator properties
        start = time.time()
        folder = (os.path.dirname(self.filepath))
        is_vhcl, is_vhcm = None, None
        for file in self.files:
            if file.name == 'body.vhcl': is_vhcl = True
            if file.name == 'body_meta.vhcm': is_vhcm = True
            if file.name != '':
                path_and_file = (os.path.join(folder, file.name))
                read_scne(context, path_and_file, **keywords)

        # Autoimport body_meta.vhcm
        if is_vhcl and not is_vhcm:
            path_and_file = (os.path.join(folder, 'body_meta.vhcm'))
            if (os.path.isfile(path_and_file)):
                read_scne(context, path_and_file, **keywords)
                show_messagebox(message="body_meta.vhcm imported", title = "Autoimporter", icon = 'INFO')

        print('\nFinished in', round(time.time()-start,2), 's')
        collapse_collections(context)
        return {'FINISHED'}

    def invoke(self, context, event):
        '''Invoke file handler if filepath is set (Drag & Drop)'''
        if self.files:
            return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ImportScneDataPh(bpy.types.Operator, ImportHelper):
    '''Imports Wreckfest SCNE as Subscene Placeholder'''
    bl_idname = "import_scene.scneph"  # this is important since its how bpy.ops.import.some_data is constructed
    bl_label = "Import SCNE as Subscene"
    bl_options = {"UNDO"}

    # ExportHelper mixin class uses this
    filename_ext = ".scne"

    filter_glob : StringProperty(default="*.scne;*.scne.raw", options={'HIDDEN'})  
    
    # Selected files
    directory: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    files : bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE'})
 
    # List of operator properties
    short_pth : BoolProperty(name="Short paths", description="Replaces data/art/objects with ob/", default=True) 
    use_color : BoolProperty(name="Use colors", description="Use semi-random colors with subscene placeholders", default=True)
    model_upd : BoolProperty(name="Update existing", description="Updates existing placeholders.\n\nDisable this option to use your customised placeholders instead of real import", default=True)
    model_onlyupd : BoolProperty(name="Placeholder update only", description="Placeholder update only. Does not place new subscene", default=False)

    def execute(self, context):
        wm = bpy.context.window_manager
        wm.progress_begin(0, len(self.files)) #load indicator
        folder = (os.path.dirname(self.filepath))
        for i, file in enumerate(self.files):
            if file.name != '':
                wm.progress_update(i)
                path_and_file = (os.path.join(folder, file.name))
                read_scne(context, path_and_file, self.short_pth, self.use_color, imp_model=True, placeholder_mode=True, model_upd=self.model_upd, model_onlyupd=self.model_onlyupd)
        wm.progress_end()
        return {'FINISHED'}

    def invoke(self, context, event):
        '''Invoke file handler if filepath is set (Drag & Drop)'''
        if self.files:
            return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ImportBmapData(bpy.types.Operator, ImportHelper):
    '''Imports Wreckfest SCNE as Subscene Placeholder'''
    bl_idname = "import_scene.bmap"  # this is important since its how bpy.ops.import.some_data is constructed
    bl_label = "Import Bmap"
    bl_options = {"UNDO"}

    # ExportHelper mixin class uses this
    filename_ext = ".bmap"

    filter_glob : StringProperty(default="*.bmap", options={'HIDDEN'})  
    
    # Selected files
    directory: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    files : bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE'})

    def execute(self, context):
        folder = (os.path.dirname(self.filepath))
        for i, file in enumerate(self.files):
            if file.name != '':
                path_and_file = (os.path.join(folder, file.name))
                import_bmap(context, path_and_file)
        return {'FINISHED'}

    def invoke(self, context, event):
        '''Invoke file handler if filepath is set (Drag & Drop)'''
        if self.files:
            return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

if bpy.app.version >= (4,1,0):
    class WM_FH_scne(bpy.types.FileHandler): # https://docs.blender.org/api/master/bpy.types.FileHandler.html
        '''Drag & Drop Handler for .vhcl'''
        bl_label = "scne"
        bl_import_operator = "import_scene.scne"
        bl_file_extensions = ".scne;.vhcl;.vhcm"

        @classmethod
        def poll_drop(cls, context):
            return context.area.type == "VIEW_3D"

    class WM_FH_scneph(bpy.types.FileHandler):
        '''Drag & Drop Handler for .scne'''
        bl_label = "scneph"
        bl_import_operator = "import_scene.scneph"
        bl_file_extensions = ".scne"

        @classmethod
        def poll_drop(cls, context):
            return context.area.type == "VIEW_3D"

    class WM_FH_bmap(bpy.types.FileHandler):
        '''Drag & Drop Handler for .bmap'''
        bl_label = "File handler for bmap node import"
        bl_import_operator = "import_scene.bmap"
        bl_file_extensions = ".bmap"

        @classmethod
        def poll_drop(cls, context):
            return ( # Drag and Drop to Shader Editor if active material
                context.region and context.region.type == 'WINDOW' and
                context.area and context.area.ui_type == 'ShaderNodeTree' and
                bpy.context.active_object and
                bpy.context.active_object.data.materials.items()
            )

class IMPORT_SCENE_OT_repair_bmapcache(bpy.types.Operator):
    """Repair Bmap Cache
\nChange all cached images location to Wreckfest\\tools\\BmapCache\\ and rebuild missing"""
    bl_idname = "import_scene.repair_bmapcache"
    bl_label = "Repair Bmap Cache"

    rebuild_all : BoolProperty(default=False) # Forces Relocate and rebuild

    @classmethod
    def poll(cls, context):
        try:
            return os.path.isdir(os.path.join(bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path,'tools'))
        except:
            return 0

    def execute(self, context):
        wf_path = bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path
        bmapcache = '\\tools\\BmapCache\\'
        bmapcache_folder = os.path.join(wf_path, bmapcache.strip('\\'))

        print ("\nRepairing Bmap Cache - ",bmapcache_folder,'\n')
        
         # load indicator
        wm = bpy.context.window_manager
        wm.progress_begin(0, len(bpy.data.images))
        count = 0

        # Find and repair Bmap Cache textures, detect by location in \tools\BmapCache\
        for image in bpy.data.images:
            count +=1
            wm.progress_update(count) # Update load indicator
            path = image.filepath.replace('/','\\')
            if bmapcache in path:
                rel_path = path.split(bmapcache)[-1]
                print (image.name,'-',rel_path, end='')
                if not self.rebuild_all and os.path.isfile(image.filepath):
                    print(" - OK")
                else:
                    # Relocate
                    new_path = os.path.join(bmapcache_folder, rel_path)
                    new_path = os.path.splitext(new_path)[0]+'.'+config.c_extension
                    if (new_path != path):
                        print(" -> RELOCATE")
                        image.filepath = new_path
                    # Reload only
                    if not self.rebuild_all and os.path.isfile(image.filepath):  
                        image.reload()
                    else: # Rebuild
                        print(" -> REBUILD")
                        bmapfile = os.path.join(wf_path, os.path.splitext(rel_path)[0]+'.bmap')

                        if os.path.isfile(bmapfile):
                            if os.path.isfile(new_path) and new_path[-5:] in ['.webp', '.cmap']:
                                os.remove(new_path) # Delete existing .webp
                            convert_bmap_file_to_image( bmapFile=bmapfile, tgaPath=new_path, quality=90, resolution=config.c_resolution, file_format='WEBP')
                            if os.path.isfile(image.filepath):
                                image.reload()
                            else:
                                print("REBUILD FAILED:")
                                print("INPUT:",bmapfile)
                                print("OUTPUT:",new_path)
                    print('\n')
        wm.progress_end()
        return {'FINISHED'}

def breckfest_locate():
    if 'wreckfest_toolbox' in __name__: # Installed as part of toolbox
        return bpy.context.preferences.addons['wreckfest_toolbox'].preferences.breckfest_path
    else: # Installed as separate addon
        return bpy.context.preferences.addons[__name__].preferences.breckfestPath

def menu_func_import(self, context):
    '''Add to File > Import Menu'''
    self.layout.operator(ImportScneData.bl_idname, text="Bugbear Scene (.scne/.vhcl)")
    self.layout.operator(ImportScneDataPh.bl_idname, text="Bugbear Scene as Subscene (.scne)")

def register(): 
    '''Only function Bblender calls on load'''
    bpy.utils.register_class(ImportScneData)
    bpy.utils.register_class(ImportScneDataPh)
    bpy.utils.register_class(ImportBmapData)
    bpy.utils.register_class(IMPORT_SCENE_OT_repair_bmapcache)
    if bpy.app.version >= (4,1,0):
        bpy.utils.register_class(WM_FH_scne)
        bpy.utils.register_class(WM_FH_scneph)
        bpy.utils.register_class(WM_FH_bmap)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(io_import_wreckfest)

def unregister():
    bpy.utils.unregister_class(ImportScneData)
    bpy.utils.unregister_class(ImportScneDataPh)
    bpy.utils.unregister_class(ImportBmapData)
    bpy.utils.register_class(IMPORT_SCENE_OT_repair_bmapcache)
    if bpy.app.version >= (4,1,0):
        bpy.utils.unregister_class(WM_FH_scne)
        bpy.utils.unregister_class(WM_FH_scneph)
        bpy.utils.unregister_class(WM_FH_bmap)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(io_import_wreckfest)


if __name__ == "__main__":
    register()



# --------------------------------------------------------------------------------
# SCNE import

class NodeGroupShader():
    '''Tools for working with node group shaders'''
    nodegroups = [] # All node groups with '#' in name
    shadernames = {} # Dictionary: [Wreckest Shader Tag : Node Group Name]
    loaded = False

    @classmethod
    def reset(self):
        self.nodegroups = []
        self.shadernames = {}
        self.loaded = False

    @classmethod
    def load(self):
        '''Load node group shaders from Toolbox'''
        try:
            bpy.ops.wf_shaders.append_wf_shaders()
        except:
            popup('Toolbox shaders not found. Imported with Principled BSDF')
        # Update available shaders list
        for groupname in bpy.data.node_groups.keys():
            if groupname.strip().startswith('#'):
                shadername = groupname.strip().split(' ', maxsplit=1)[0]
                self.nodegroups += [groupname]
                self.shadernames.update({shadername: groupname})
        if '#pbr' in self.shadernames:
            self.loaded = True
        # Default shaders (used by importer)
        if '#pbr Default' in self.nodegroups:
            self.shadernames.update({'#pbr': '#pbr Default'})
        if '#blend' in self.nodegroups:
            self.shadernames.update({'#blend': '#blend'})

    @classmethod
    def find(self, matName, simpleBlendmat=False):
        '''Find node group for material'''
        # Detect special #blend shader
        if '#blend' in matName and not simpleBlendmat and '#blend Advanced' in self.nodegroups:
            return bpy.data.node_groups['#blend Advanced']
        # Detect by material #tag
        shader = self.find_shader_for_mat(matName)
        if(shader):
            return shader
        # Default to '#pbr Default' shader
        return bpy.data.node_groups[self.shadernames['#pbr']]

    @classmethod
    def find_shader_for_mat(self, matName):
        '''Find node group with tag matching to material'''
        for shader_name in self.shadernames:
            if shader_name in matName:
                return bpy.data.node_groups[self.shadernames[shader_name]]
        return False
        
def show_messagebox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def popup(title):
    '''Error popup'''
    show_messagebox("Error", title, 'ERROR')
    print(title) # error to console


def text_to_color(text):
    '''Generate color for placeholder'''
    random.seed(text)
    r = random.random()*1.5
    g = random.random()*1.5
    b = random.random()*1.5
    if(r>1): r=1
    if(g>1): g=1
    if(b>1): b=1
    return (r,g,b,1)


def hashy(name):
    '''Generate short md5 hash'''
    return hashlib.md5(name.encode('utf-8')).hexdigest()[0:8]

def check_meshdata(verts, faces, name=''):
    '''Check that all vert references are within valid range'''
    maxvert = len(verts)  
    for face in faces:
        for x in face:
            if(x<0 or x>(maxvert-1)): 
                popup("\nIncorrect triangle data at "+name+", reference to vert: "+str(x)+"\n")
                return False
    return True

def from_pydata_safe(mesh, verts, ee, faces):
    '''Generate mesh only if all vert references are valid'''
    if (check_meshdata(verts,faces)):
        mesh.from_pydata(verts, [], faces)
        mesh.update()
    return mesh


def origin_to_geometry(ob):
    '''Reset object origin to average coordinate'''
    center = mathutils.Vector((0, 0, 0))
    numVert = 0
    oldLoc = ob.location
    for v in ob.data.vertices: # Sum all
        center += v.co # x,y,z
        numVert += 1
    center = center/numVert # Divide to get average point
    movement = oldLoc - center
    for v in ob.data.vertices: # Move all vertices
        v.co += movement
    ob.location -= movement # Move object to opposite direction

def create_mesh_ob(name, verts, faces, meshname='', collection='', matrix='', reset_origin=True, draw_type='TEXTURED', show_wire=False, color='', colorname='', subCollection=False, use_nodes=False):
    '''Create object from list of verts and faces'''
    if (check_meshdata(verts,faces,meshname) == False): return False

    mesh = bpy.data.meshes.new(meshname)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    
    ob = bpy.data.objects.new(name, mesh)
    ob.display_type = draw_type
    ob.show_wire = show_wire
    if matrix != '':
        ob.matrix_world = matrix

    # Create new material or use existing
    if (color != '' and colorname != ''):
        if (colorname in bpy.data.materials):
            mat = bpy.data.materials.get(colorname)
        else:
            mat = bpy.data.materials.new(colorname)
            mat.diffuse_color = color
            if(use_nodes):
                mat.use_nodes = True
                node = mat.node_tree.nodes["Principled BSDF"]
                node.inputs[0].default_value = color[0], color[1], color[2], 1
                node.inputs['Alpha'].default_value = color[3]
                if(color[3]<1):
                    mat.blend_method = 'BLEND'
        ob.active_material = mat


    link_to_collection(ob, collection)
    if(reset_origin): origin_to_geometry(ob)

    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob

def create_cube_ob(name, size=1.0, meshname='', collection='', matrix=''):
    '''Create cube object'''
    if(meshname==''): meshname=name
    bm = bmesh.new()
    if(matrix==''): bmesh.ops.create_cube(bm, size=size)
    else: bmesh.ops.create_cube(bm, size=size, matrix=matrix)
    mesh = bpy.data.meshes.new(meshname)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    link_to_collection(ob, collection)
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob

def create_empty_ob(name, type='CUBE', size=1.0, collection=''):
    '''Create empty object'''
    ob = bpy.data.objects.new(name, object_data=None)
    link_to_collection(ob, collection)
    ob.empty_display_size = size
    ob.empty_display_type = type
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob

def create_light_ob(name, type='POINT', color=[1,1,1], power=10, collection=''):
    '''Create light object'''
    l_data = bpy.data.lights.new(name=name, type=type)
    l_data.color = [*color]
    l_data.energy = power
    ob = bpy.data.objects.new(name, object_data=l_data)
    link_to_collection(ob, collection)
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob
    
def shorthand_path(scne_name,filepath):
    '''Shorten #xref placeholder names using predefined ob/ le/ ba/ ed/ prefix'''
    scne_name = scne_name.replace("data/art/objects/", "ob/")
    scne_name = scne_name.replace("data/art/levels/", "le/")
    scne_name = scne_name.replace("data/art/base/", "ba/") # rru
    scne_name = scne_name.replace("data/art/editor/", "ed/") # rru
    if(bpy.data.is_saved): 
        filepath = bpy.data.filepath # use saved .blend folder as relative path
    else: 
        filepath = filepath.replace('/', '\\') # use folder of import as relative path, f
    if('\\data\\' in filepath): # replace current blend path with //
        pth = to_wf_path(filepath) # keep after /data/
        pth = pth.rsplit('/',1)[0] # remove filename from path
        scne_name = scne_name.replace(pth+"/", "//")
    return scne_name

def to_wf_path(filepath): 
    '''Convert filepath to Wreckfest relative data/.. path'''
    path = filepath.replace('\\', '/')
    path = "data/" + re.split("/data/", path)[-1] # remove everything before /data/
    return path

def new_collection(collectionName, parentCollection=''):
    '''Create collection'''
    col = bpy.data.collections.new(collectionName)
    parent = bpy.context.scene.collection.children.get(parentCollection)
    if parentCollection == '': # Add to requested collection.
        bpy.context.scene.collection.children.link(col)
    elif parent: # Add to sub-collection instead.
        parent.children.link(col)
        
def link_to_collection(obj, collectionName):
    '''Add to collection. Will create new collection if needed'''
    if(collectionName==''):
        bpy.context.scene.collection.objects.link( obj )
    else:
        if collectionName not in bpy.data.collections: new_collection(collectionName) # make new collection
        layer = bpy.context.view_layer.layer_collection # Current view layer Collection
        if(collectionName in layer.children and layer.children[collectionName].exclude == False): # Prevent error by excluded collection
            bpy.data.collections[collectionName].objects.link( obj ) # add to collection, 
        else:
            bpy.context.scene.collection.objects.link( obj ) # add without collection, if collection excluded or moved to subcollection.

def apply_matrix(verts, mx):
    '''Apply transform matrix to verts data'''
    x, y, z = verts
    xnew = x*mx[0][0] + y*mx[1][0] + z*mx[2][0] + mx[3][0]
    ynew = x*mx[0][1] + y*mx[1][1] + z*mx[2][1] + mx[3][1]
    znew = x*mx[0][2] + y*mx[1][2] + z*mx[2][2] + mx[3][2]
    return [xnew, ynew, znew]

def fix_lod(string):
    '''Remove '_lod' and '#lod' from name'''
    if __name__+'.uv' in sys.modules: return string
    return re.sub('(?i)[_#](lod)[0-9]', '', string) 

def save_image(image, filename, format, quality=90):
    '''Save image from bpy.data.images to disk'''
    print('Saving   : ',filename)
    os.makedirs(os.path.dirname(filename), exist_ok=True) 

    s = bpy.context.scene.render.image_settings
    backup = s.file_format, s.color_mode, s.quality # Backup
    s.file_format = format # Change format temporarily for saving
    s.color_mode = 'RGBA'
    s.quality = quality
    image.save_render(filename)
    s.file_format, s.color_mode, s.quality = backup # Restore

def convert_bmap_file_to_image(bmapFile, tgaPath, quality=90, resolution=256, file_format='TARGA'):   
    '''Open .bmap file on disk and save as .tga or .webp'''
    # File_formats: https://docs.blender.org/api/current/bpy_types_enum_items/image_type_items.html#rna-enum-image-type-items
    breckfest_location = breckfest_locate()
    tempFolder = tempfile.gettempdir() # Windows: C:\users\user\AppData\Local\Temp 

    args = [breckfest_location, bmapFile]
    if sys.platform != 'win32':  args = [config.wine_cmd] + args # In Linux run .exe with wine
    print("\n"+' '.join(args))
    #exe_str = '"'+breckfest_location+'" "'+bmapFile+'"'
    #print(exe_str,'\n')

    if os.path.isfile(breckfest_location) and not os.path.isfile(tgaPath):
        subprocess.run(args,  cwd = tempFolder, timeout = 60) # run = wait for Breckfest to finish, cwd = folder of unpack 

        noExtension = tempFolder +'\\'+ bmapFile.split('\\')[-1][:-5] 

        for ext in ['.dxt1.png', '.dxt5.png', '.ati2.png']: # Check if Breckfest unpacked file found.
            if os.path.isfile(noExtension + ext):
                foundPng = noExtension + ext
                image = bpy.data.images.load(foundPng) # check_existing=True
                image.colorspace_settings.name = 'Non-Color' # Keeps colors intact during save.
                break
        else: # File not found, exiting
            print("Error: Breckfest generated file not found.")
            return 

        # Resize image
        x, y = image.size
        while(x*y > resolution*resolution):
            x = x/2
            y = y/2
        if not __name__+'.uv' in sys.modules:
            image.scale(int(x),int(y))

        if not os.path.isfile(tgaPath): save_image(image, tgaPath, file_format, quality)
        os.remove(foundPng) # delete png file made by Breckfest
        bpy.data.images.remove(image) # remove file from Blender memory

def image_refer(fileName, fullPath):
    '''Image loading for images that may not exist yet'''
    image = bpy.data.images.new(fileName, width=1, height=1) # add new 1x1 px internal image
    image.source = 'FILE' # overwrite with external image
    image.filepath = fullPath
    image.generated_type ='UV_GRID'
    return image

def add_mapping_node(scale, linkOutputTo, material, YLocation):
    '''Add mapping node. Used for importing #blend material mapping'''
    if ('WF Mapping' in bpy.data.node_groups): # Try use Bugmenu mapping node
        mapping_node = material.node_tree.nodes.new('ShaderNodeGroup')
        mapping_node.node_tree = bpy.data.node_groups['WF Mapping'] 
        mapping_node.inputs['Scale'].default_value = scale # X,Y,Z Vector
    else: # Fallback to Built-in mapping node
        mapping_node = material.node_tree.nodes.new('ShaderNodeMapping')
        if bpy.app.version >= (2,83):
            mapping_node.inputs['Scale'].default_value = scale # X,Y,Z Vector
    mapping_node.location = (-450,YLocation)
    material.node_tree.links.new(linkOutputTo.inputs['Vector'], mapping_node.outputs['Vector'])
    return mapping_node

def add_wf_material(txtrList,matName,filepath,spec,gloss,imp_tga,textureUV,textureScale):
    if bpy.app.version >= (4,00):
        wf_bsdf_slots = [
            'Transmission Weight', # 0
            'Base Color', # 1
            'Specular IOR Level', # 2
            'Specular Tint', # 3
            'Roughness', # 4
            'Emission Color', # 5
            'Alpha', # 6
            'Anisotropic', # 7
            'Normal', # 8
            'Coat Weight', # 9
            'IOR', # 10
            'Tangent', # 11
        ]
    else:
        wf_bsdf_slots = [
            'Transmission', # 0
            'Base Color', # 1
            'Specular', # 2
            'Specular Tint', # 3
            'Roughness', # 4
            'Emission', # 5
            'Alpha', # 6
            'Anisotropic', # 7
            'Normal', # 8
            'Clearcoat', # 9
            'IOR', # 10
            'Tangent', # 11
        ]

    simpleBlendmat = ("#blend" in matName.lower() and len(txtrList) == 12) # Assuming blindlly materials with 12 textures and #blend use only 4 input materials shortcut
    blendMatTranslate =  {6:0, 0:1, 2:2, 4:3} # Blend, red, green blue

    importFolder = filepath.rsplit("\\", maxsplit=1)[0] + '\\' # folder of file being imported
    blendFolder = bpy.path.abspath("//") # folder of saved blend file
    dataFolderImport = importFolder.split('\\data\\', maxsplit=1)[0] + '\\' # data folder of file being imported
    dataFolderBlend = blendFolder.split('\\data\\', maxsplit=1)[0] + '\\' # data folder of saved blend file

    if(bpy.data.is_saved and '\\data\\' in blendFolder): # Comparing folder of .blend to /data/ in path
        dataFolder = dataFolderBlend
        relativeTo = blendFolder
    elif('\\data\\' in importFolder): # Comparing folder of import .scne to /data/ in path
        dataFolder = dataFolderImport
        relativeTo = importFolder
    else:
        dataFolder = importFolder # nonsense bugfix
        relativeTo = importFolder

    if (matName in bpy.data.materials):  mat = bpy.data.materials.get(matName)
    else: 
        mat = bpy.data.materials.new(matName)
        mat.specular_intensity = spec
        mat.roughness = gloss
        mat.use_nodes = True
        if(len(txtrList)>0 and '#car_body' not in matName): # Set viewport transparency
            tgaPath = txtrList[0][1].lower()
            if(txtrList[0][0] == 1 and ('_c1.' in tgaPath or '_c5.' in tgaPath)): # 1 = diffuse color
                mat.blend_method = 'CLIP'

        # Material output node
        outNode = mat.node_tree.nodes["Material Output"]
        outNode.location = (400,300)

        if(NodeGroupShader.loaded):
            wftbNode = mat.node_tree.nodes.new('ShaderNodeGroup')
            wftbNode.node_tree = NodeGroupShader.find(matName, simpleBlendmat)
            wftbNode.location = (100,300)
            wftbNode.width = 240
            mat.node_tree.nodes.remove(mat.node_tree.nodes["Principled BSDF"]) # Delete default node
            mat.node_tree.links.new(wftbNode.outputs[0], outNode.inputs[0])
        else:   
            bsdfNode = mat.node_tree.nodes["Principled BSDF"]
            bsdfNode.location = (100,300)

        # #blend uv nodes
        if("#blend" in matName.lower()):
             uvNode1 = mat.node_tree.nodes.new('ShaderNodeUVMap')
             uvNode1.uv_map = "UVMap"
             uvNode1.location = (-650,300)
             uvNode2 = mat.node_tree.nodes.new('ShaderNodeUVMap')
             uvNode2.uv_map = "UVMap2"
             uvNode2.location = (-650,-120)

        # Add Image Texture nodes
        for tx in txtrList:
            key = tx[0]
            if(not simpleBlendmat or (key in blendMatTranslate.keys())): # Normal material, or 4 chosen Blendmap textures ok (ignoring auto generated materials)
                if(simpleBlendmat): key = blendMatTranslate[key] # Translate Blendmat keys 
                bmapPath = tx[1].replace('/','\\') # 'data\art\objects...
                tgaPath = bmapPath.replace('.bmap', '.tga') # 'data\art\objects...
                fileName = tgaPath.split('\\')[-1]

                imageNode = mat.node_tree.nodes.new('ShaderNodeTexImage')
                imageNode.hide = True # Collapse node
                nodeYLocation = 300+key*50*-1 # Nodes in key order
                imageNode.location = (-250,nodeYLocation)

                # Create texture node
                if (fileName in bpy.data.images): # use existing image with same name
                    imageNode.image = bpy.data.images.get(fileName) 
                else: # Make new image

                    # Save tga files on disk
                    if(imp_tga and '\\data\\' in blendFolder and '\\mods\\' in blendFolder):
                        if(bmapPath.split('_')[-1].lower() in ['c.bmap', 'c1.bmap', 'c5.bmap']): #Allowed extensions
                            convert_bmap_file_to_image( bmapFile=dataFolderImport+bmapPath, tgaPath=dataFolderBlend+tgaPath )

                    # Link in Shader Node new image datablock with relative reference to file
                    imageNode.image = image_refer(fileName, fullPath=bpy.path.relpath(dataFolder+tgaPath,start=relativeTo)) 

                # Connect texture to shader node
                if not NodeGroupShader.loaded: # Principled BSDF
                    mat.node_tree.links.new(bsdfNode.inputs[wf_bsdf_slots[key]], imageNode.outputs['Color'])
                else: # Shader Nodegroup
                    if len(wftbNode.inputs) > key:
                        mat.node_tree.links.new(wftbNode.inputs[key], imageNode.outputs['Color'])
                        # Connect alpha of second texture to special nodegroup alpha
                        if(key==1 and not "#blend" in matName.lower() and ('_c1.' in tgaPath or '_c5.' in tgaPath)):
                            mat.node_tree.links.new(wftbNode.inputs['Alpha'], imageNode.outputs['Alpha'])

                # #blend scale mapping and uv node links
                if("#blend" in matName.lower()):
                    connect_uv_to = imageNode
                    # Add mapping if scale exists
                    if (key in textureScale and (textureScale[key][0]!=1 or textureScale[key][1]!=1)):
                        mapping_node = add_mapping_node(scale=textureScale[key], linkOutputTo=imageNode, material=mat, YLocation=nodeYLocation)
                        connect_uv_to = mapping_node
                        if (key in [0,2,4,7] and key in textureUV): # Connect Albedo UV 1 only with mapping node
                            if textureUV[key] == 0:
                                mat.node_tree.links.new(mapping_node.inputs[0], uvNode1.outputs[0])

                    # Connect Albedo UV 2 always
                    if (key in [0,2,4,7] and key in textureUV):
                        if textureUV[key] == 1: # 1 = UV2
                            mat.node_tree.links.new(connect_uv_to.inputs[0], uvNode2.outputs[0])
                    # Last slots connect to UV2 always
                    if (key in [6,9,10,11]): # UV2 used by last slots
                        mat.node_tree.links.new(connect_uv_to.inputs[0], uvNode2.outputs[0])


def make_meshes(get,filepath,imp_mat,matrix,modelName,imp_tga):
    '''MESH import'''
    allMatNames = []
    get.i() #0 version
    numMesh = get.i()
    for mId in range(0, numMesh):
        meshName = get.wftext()

        get.checkHeader('btch')
        get.i() #2 version
        numBatch = get.i()
        matName = ''
        matNames = []
        currentMatId = -1
        verts = []
        triangles = []
        #normals = []
        triMatIdlist = []
        #vertGroups = [[]]*40
        vertGroups = [[] for _ in range(256)]
        vertId = -1
        uvs = []
        uvs2 = []
        voffset = 0
        for yy in range(0, numBatch):
            biasX, biasZ, biasY, biasW = get.f(), get.f(), get.f(), get.f()
            minX, minZ, minY = get.f(), get.f(), get.f() #BBox Min
            maxX, maxZ, maxY = get.f(), get.f(), get.f() #BBox Max

            get.checkHeader('mtrl')
            matversion = get.i() # version: rru 4, wf 7, wf2 18
            numMtrl = get.i()
            if(numMtrl != 0): # Check only first material
                matName = get.wftext()
                get.i() # Shader Id
                get.i() # Priority
                spec = get.f() # Specular
                gloss = get.f() # Glossiness
                textureScale = {}
                textureUV = {}
                uvTile = get.f(), get.f(), 1  # Detail/macro Map Tiling U, V (key 7: detailblend)
                textureScale[7] = uvTile
                XScale = 0,0,0,0
                YScale = 0,0,0,0
                if(matversion > 4): # Misc Param 0 & 1 # not in rru
                    # Misc Param 0, albedo/detailblend UV channel select for #blend 
                    textureUV[0] = int(get.f()) # key 0: #blend 1st abledo
                    textureUV[2] = int(get.f()) # key 2: #blend 2nd abledo
                    textureUV[4] = int(get.f()) # key 4: #blend 3rd abledo
                    textureUV[7] = int(get.f()) # key 7: #blend detailblend
                    # Misc Param 1, albedo/detailblend scale for #blend 
                    XScale = get.f(), get.f(), get.f(), get.f()
                if(matversion > 6): #Misc Param 2
                    YScale = get.f(), get.f(), get.f(), get.f() # albedo/detailblend scale for #blend 
                    textureScale[0] = XScale[0], YScale[0], 1.0
                    textureScale[2] = XScale[1], YScale[1], 1.0
                    textureScale[4] = XScale[2], YScale[2], 1.0 
                    #textureScale[7] = XScale[3], YScale[3], 1.0 
                
                if(matName not in matNames):
                    matNames.append(matName)
                    allMatNames.append(matName)
                    currentMatId += 1
                txtrList = []

                if(1e30<=uvTile[0]):
                    return (get.text(), matName, 'txtr')

                get.checkHeader('txtr')
                if(imp_mat):
                    get.i() # version
                    numText = get.i()
                    for yyy in range(0, numText):
                        typee = get.i() # Type

                        if(get.checkHeader('bmap')): # Check against empty section in place of bmap
                            bmapPath = get.wftext()
                            txtrList.append([typee,bmapPath])

                    if (imp_mat): add_wf_material(txtrList,matName,filepath,spec,gloss,imp_tga,textureUV,textureScale)

                if(matversion>4): # not in rru
                    get.checkHeader('cltr')
                    # Clutter code not done yet

            get.skipToHeader('vert')
            version = get.i() # version: rru 3, wf 4
            numVert = get.i()
            newVersion = version > 3
            # Numpy is fastest way to interpret bytes
            e = get.endian # rru big endian, wf little endian
            dtypes = [
            ('x', e+'i2'), # Position
            ('z', e+'i2'),
            ('y', e+'i2'),
            ('w', e+'i2'),
            ('nx', 'u1'), # Normal
            ('ny', 'u1'),
            ('nz', 'u1'),
            ('nw', 'u1'),
            ('uvx', e+'i2'), # Uv0
            ('uvy', e+'i2'),
            ]
            if(newVersion): # New wf format
                dtypes += [
                ('nx2', 'u1'), # Normal1, Integer 0-255 where 0=-1, 127=0, 255=1
                ('ny2', 'u1'),
                ('nz2', 'u1'),
                ('nw2', 'u1'),
                ('uvx2', e+'i2'), # Uv1
                ('uvy2', e+'i2'),
                ('b_id1', 'u1'), # Bone Index / Vertex group id
                ('b_id2', 'u1'),
                ('b_id3', 'u1'),
                ('b_id4', 'u1'),
                ('b_w1', 'u1'), # Bone Weight / Vertex weight in group
                ('b_w2', 'u1'),
                ('b_w3', 'u1'),
                ('b_w4', 'u1'),
                ]
            dtype = np.dtype(dtypes)
            rawdata = get.readBytes(dtype.itemsize*numVert) # Read all verts
            for vert in np.frombuffer(rawdata, dtype=dtypes, count=-1).tolist():
                vertId += 1
                if(newVersion):
                    x, z, y, w, nx, ny, nz, nw, uvx, uvy, nx2, ny2, nz2, nw2, uvx2, uvy2, b_id1, b_id2, b_id3, b_id4, b_w1, b_w2, b_w3, b_w4 = vert
                    if('skin' in matName): # Limit slow weight import to #uber_skin shader n similar
                        vertGroups[b_id1].append((vertId, b_w1/255)) # 0-255 to 0-1 range
                        vertGroups[b_id2].append((vertId, b_w2/255))
                        vertGroups[b_id3].append((vertId, b_w3/255))
                        vertGroups[b_id4].append((vertId, b_w4/255))
                    uvs2.append((uvx2, uvy2))
                else:
                    x, z, y, w, nx, ny, nz, nw, uvx, uvy = vert

                verts.append((x*biasW+biasX, y*biasW+biasY, z*biasW+biasZ))
                uvs.append((uvx, uvy))
                #normals.append(((nx-127)/128, (nz-127)/128, (ny-127)/128))


            get.checkHeader('tria')
            get.i() # version
            numTri = get.i()
            # Numpy is fastest way to interpret bytes
            rawdata = get.readBytes(6*numTri) #Tri data = 6 bytes
            dtype = np.dtype([
                ("a", e+"u2"),    
                ("c", e+"u2"),
                ("b", e+"u2"),
                ])
            for tri in np.frombuffer(rawdata, dtype=dtype, count=-1).tolist():
                a, c, b = tri
                triangles.append((a+voffset,b+voffset,c+voffset))
                triMatIdlist.append(currentMatId)
            voffset = voffset + numVert

            if(matversion<18):
                get.checkHeader('edgm')
                get.i() # version
                for v in range(0, get.i()):
                    get.wfdata()
                    get.wfdata()
                    get.wfdata()
                    get.wfdata()

    if(numMesh>0): # Only real mesh, Shadowmeshes may not have actual mesh
        ob = create_mesh_ob(fix_lod(meshName), verts, triangles, meshname=meshName, matrix=matrix, collection="Models", reset_origin=False, subCollection=True)
        try:
            uv.uv(ob.data,uvs)
            if (any([x[0]!=0 for x in uvs2])):
                uv.uv(ob.data,uvs2)
        except NameError:
            pass

        # setting materials (just names, not actual materials)
        if(imp_mat):
            matNames = list(dict.fromkeys(matNames+allMatNames)) # remove duplicates. Add unused materials from allMatNames to end.
            for matName in matNames:
                if (matName in bpy.data.materials):  mat = bpy.data.materials.get(matName)
                else: mat = bpy.data.materials.new(matName)
                ob.data.materials.append(mat)
            # Assign material
            ob.data.polygons.foreach_set("material_index", triMatIdlist)
            #ob.data.use_auto_smooth = True
            #ob.data.normals_split_custom_set_from_vertices(normals)
            i = 0
            for group in vertGroups:
                if len(group)>0:
                    newGroup = ob.vertex_groups.new(name=str(i))
                    for vertData in group:
                        vertId, bone_weight = vertData
                        newGroup.add([vertId], bone_weight, 'ADD')
                i += 1
    if(numMesh>0):
        return ob
    return ''




def hex2rgba(h):
    h = h.lstrip('#')
    "".join(reversed([h[i:i+2] for i in range(0, len(h), 2)]))
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0, 2, 4, 6))

def surf2rgba(s):
    if "default" in s: return hex2rgba("#E7E7E7FF")
    elif "reset" in s: return hex2rgba("#E60000F2")
    elif "barrier" in s: return hex2rgba("#00E600FF")
    elif "foliage" in s: return hex2rgba("#36781AFF")
    else: return text_to_color(s)

def shift_vert(v):
    return int.from_bytes(v, byteorder='little', signed=True) // 6

def shift_float(v):
    return int.from_bytes(v, byteorder='little', signed=True) / 0xFFFF

def shpe_read_tri(sh):
    a, b, c = sh.readBytes(3), sh.readBytes(3), sh.readBytes(3)
    return [shift_vert(a), shift_vert(b), shift_vert(c)]

def shpe_read_vector3(sh, debug = False):
    x, z, y = sh.readBytes(), sh.readBytes(), sh.readBytes()
    #if debug:
    #    print(binascii.hexlify(x))
    #    print(binascii.hexlify(y))
    #    print(binascii.hexlify(z))
    return [shift_float(x), shift_float(y), shift_float(z)]

def collapse_collections(context):
    if bpy.app.version >= (3,2): #temp override is new feature
        try:
            # Need this or else newly created collections won't collapse.
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1) 
            area = next(a for a in context.screen.areas if a.type == 'OUTLINER')
            with context.temp_override(area=area):
                bpy.ops.outliner.show_hierarchy('INVOKE_DEFAULT')
                for i in range(2):
                    bpy.ops.outliner.expanded_toggle()
            area.tag_redraw()
        except: pass # outliner screen area might be missing

def shpe_get_bias(b):
    bias = [1,1,1]
    for i in range(3):
        delta = 18304.3 - round(b[i],1)
        if delta > 0:
            bits = 6
            while bits > 0:
                thresh = 1 << bits
                if delta > thresh:
                    bias[i] = delta / thresh
                    break
                bits -= 1
    return bias

def get_surface_tag(id):
    '''Convert collision shape surface id to surface tag like #asphalt.'''
    surfacelist = ['default','gravel','graveldark','gravelpacked','mud','offroadrocks','offroadfoliage','offroadsand',
        'asphalt','concrete','metal','water','wood','nofriction','slowdown','slowdownsand','foliage','wettarmac','killplayer',
        'resetplayer','curb','asphaltdusty','offroadasphalt','blender_glass','superslowdown','gravelredclay','global_barrier',
        'concrete_barrier','metal_barrier','speedup','loop','resetplayer_delay','snow','crm_solid','crm_water_reset']
    if id<len(surfacelist):
        return str(id)+'#'+surfacelist[id]
    else:
        return str(id)+'-'+'unknown'

def make_shape(shpedata, modelname, matrix, debug):
    '''SHAPE import (collision)'''
    sh = BagParse(shpedata)
    length = len(sh.bytes)
    # Skip unknown constants (8 B). 
    # Skip bounding box (24 B).
    # Skip first bias (12 B).
    sh.skip(44)
    bias = shpe_read_vector3(sh)
    bias = shpe_get_bias(bias)
    # Calculate tri/vert count from length values.
    fLen = sh.i()
    tLen = sh.i() - fLen
    # Skip face count data, calculate based on lengths.
    sh.skip(fLen)
    # Triangle struct is 11 bytes (1B+1B+3*3B).
    numTris = tLen // 11
    # Vertex struct is 24 bytes (6*4B).
    # 64B = 2*constant(8B) + 2*bb(24B) + 2*bias(24B) + 2*lens(8B)
    numVerts = (length - 64 - tLen - fLen) // 24
    verts = []
    tris = []
    surfs = []
    surfVerts = []
    for f in range(numTris):
        # B = Unsigned char https://docs.python.org/3/library/struct.html
        ids = sh.read('BB') 
        tri = shpe_read_tri(sh)
        tris += tri,
        if not ids[1] in surfs:
            surfs.append(ids[1])
            surfVerts.append([])
        index = 0
        for s in surfs:
            if s == ids[1]:
                surfVerts[index].append(tri)
                break
            index += 1
    # There can be padding bytes after triangle data.
    sh.skip(-sh.tell() + 0x40 + tLen + fLen)
    for v in range(numVerts):
        pos = shpe_read_vector3(sh)
        sh.skip(12) # Skip normals.
        verts += [pos[0]*bias[0], pos[1]*bias[1], pos[2]*bias[2]],
    

    ### Create Shape ###
    ob = create_mesh_ob(modelname, verts, tris, modelname, collection="Models-collision", matrix=matrix, reset_origin=False, draw_type='TEXTURED', show_wire=False)

    # Add vertices into groups for each surface.
    for i in range(0, len(surfs)):
        id = surfs[i]
        colorname = get_surface_tag(id)

        if (colorname in bpy.data.materials):  mat = bpy.data.materials.get(colorname)
        else: mat = bpy.data.materials.new(colorname)
        mat.roughness = 1.0
        if (debug): color = text_to_color(colorname[1:]) # Use random color
        else: color = hex2rgba("#E60000F2") # Use red color for all surfaces outside of debug mode
        mat.diffuse_color = color
        ob.data.materials.append(mat)
        vgroup = ob.vertex_groups.new(name=colorname)
        for v in surfVerts[i]:
            vgroup.add(v, 1.0, 'ADD')
    # Assign tris to respective materials.
    for p in ob.data.polygons:
        vgroup = [g.group for v in p.vertices for g in ob.data.vertices[v].groups]
        counts = [vgroup.count(id) for id in vgroup]
        modeIndex = counts.index(max(counts))
        groupName = ob.vertex_groups[vgroup[modeIndex]].name
        index = ob.material_slots.find(groupName)
        p.material_index = index
    return ob


def make_models(get,filepath,short_pth,imp_anim,imp_mat,imp_tga,debug,imp_shpe=False):
    '''MODELS import'''
    mdl_version = get.i() # version: rru 0, wf 5, wf2 6

    if mdl_version >= 6: # Disable models import for Wreckfest 2
        return

    nummdl = get.i() # number of models
    print ("\nFound",nummdl,"Models")
    wm = bpy.context.window_manager
    wm.progress_begin(0, nummdl) # load indicator
    render_fps = bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
    for x in range(0, nummdl):
        ob=''
        if(x%10==0): wm.progress_update(x) # load indicator update every 10th
        modelname = get.wftext()
        DynamicTypeString = get.wftext()
        if(str(chr(163)) in DynamicTypeString): return None 
        if(mdl_version>0): # wf
            get.text(4)
            get.wftext()
        matrix = get.matrix()
        aabb = get.f(), get.f(), get.f(), get.f(), get.f(), get.f() 
        cx, cz, cy, ex, ez, ey = aabb

        get.checkHeader('pmsh') # Base Mesh
        version = get.i() #1 version
        numBaseMesh = get.i()
        for y in range(0, numBaseMesh):
            get.aabb()
            if(get.checkHeader('mesh')): # If = Check against empty section in place of mesh, Mainmesh
                ob = make_meshes(get,filepath,imp_mat,matrix,modelname,imp_tga) # Base mesh to ob to add animations later
            if(version > 0):
                if(get.checkHeader('mesh')): # Shadowmesh
                    make_meshes(get,filepath,imp_mat,matrix,modelname,imp_tga)

        get.checkHeader('pmsh') # Damage Mesh
        version = get.i() #1 version
        numDmgMesh = get.i()
        for y in range(0, numDmgMesh):
            get.aabb()
            if(get.checkHeader('mesh')): # If = Check against empty section in place of mesh, Mainmesh
                make_meshes(get,filepath,imp_mat,matrix,modelname,imp_tga)
            if(version > 0):
                if(get.checkHeader('mesh')): # Shadowmesh
                    make_meshes(get,filepath,imp_mat,matrix,modelname,imp_tga)

        get.checkHeader('shpe')
        version = get.i()
        numShapes = get.i()
        if(version==0): numShapes = 0 # skip rru/version 0, not implemented
        i=0
        for x in range(0, numShapes):
            get.i() #type
            shpedata = get.wfdata()
            if(imp_shpe):
                if ob=='': # If not base mesh, import collision mesh
                    ob = make_shape(shpedata, modelname, matrix, debug)
                elif debug: # debug mode imports all
                    make_shape(shpedata, modelname, matrix, debug)

            get.checkHeader('shbx')
            get.i() # version
            numShapebox = get.i()
            # Make #col collision cubes for dynamic objects
            for y in range(0, numShapebox): 
                i = i+1
                # Create an empty mesh 
                mesh = bpy.data.meshes.new(modelname+"#col"+str(i))
                bm = bmesh.new()
                shapeMx = get.matrix()
                shapeAabb = get.f(), get.f(), get.f(), get.f(), get.f(), get.f()
                cx, cz, cy, ex, ez, ey = shapeAabb
                # Skip if default shape box
                defaultMx = (1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)  
                if(numShapebox==1 and shapeMx==defaultMx and shapeAabb==aabb):
                    break
                mx = mathutils.Matrix.Translation((cx, cy, cz))
                mx = mx @ mathutils.Matrix.Scale(ex*2, 4, (1.0, 0.0, 0.0))
                mx = mx @ mathutils.Matrix.Scale(ey*2, 4, (0.0, 1.0, 0.0))
                mx = mx @ mathutils.Matrix.Scale(ez*2, 4, (0.0, 0.0, 1.0))

                bmesh.ops.create_cube(bm, size=1.0, matrix=mx)

                for v in bm.verts: # apply transform matrix
                    v.co.x, v.co.y, v.co.z = apply_matrix((v.co.x, v.co.y, v.co.z), shapeMx)

                bm.to_mesh(mesh)
                bm.free()

                # Create the object
                o = bpy.data.objects.new(modelname+"#col"+str(i), mesh)

                # Add the object into the scene.
                link_to_collection(o, "Models#col")
                o.matrix_world = matrix # set transformation
                bpy.context.view_layer.objects.active = o
                o.select_set(True) 

        get.skipToHeader('anim')
        
        if(imp_anim):
            get.i() # version
            numAnim = get.i() # Number of Animations
            for x in range(0, numAnim):
                get.checkHeader('kfra')
                get.i() # version
                numKfra = get.i() # Number of keyframes
                for y in range(0, numKfra):
                    rot = get.f(), get.f(), get.f(), get.f()
                    loc = get.f(), get.f(), get.f() #X Z Y
                    timeS = get.f() # Seconds
                    frame = timeS*render_fps
                    if(ob!=''):
                        #ob.rotation_euler = rot[0], rot[2], rot[1]
                        ob.rotation_mode = 'QUATERNION'
                        ob.rotation_quaternion = rot[3], rot[0]*-1, rot[2]*-1, rot[1]*-1  # wxyz blender, xzyw wreckfest
                        ob.location = loc[0], loc[2], loc[1]
                        ob.keyframe_insert(data_path="location", frame=frame)
                        ob.keyframe_insert(data_path="rotation_quaternion", frame=frame)

            if(numKfra>0):
                bpy.context.scene.frame_start = 0       
                if(bpy.context.scene.frame_end < frame):
                    bpy.context.scene.frame_end = math.ceil(frame)


        if mdl_version >= 5: # Skin import not tested in versions below 5
            get.skipToHeader('skin')
            get.i() # version
            edit_mode = False
            for x in range(get.i()):
                get.checkHeader('bone')
                get.i() # version
                numBone = get.i() # Number of skin bones
                # Create Armature, not finished, only in debug mode
                if(numBone>0 and debug):
                    arm = bpy.data.armatures.new('Armature')
                    arm_ob = bpy.data.objects.new(modelname+'-Bones', arm)
                    link_to_collection(arm_ob, "Models-Skin")
                    bpy.context.view_layer.objects.active = arm_ob
                    arm_ob.select_set(True) 
                    arm_ob.show_in_front = True
                    # Armature deform modifier
                    ob.parent = arm_ob
                    modifier = ob.modifiers.new(name="Armature", type='ARMATURE') # Add
                    modifier.object = arm_ob
                    # Add bones only if edit mode can be switched on
                    try:
                        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                        edit_mode = True
                    except: 
                        popup('Error: Edit mode not available. Skipping Skin bone import.') 

                for boneId in range(0, numBone):
                    name = get.wftext()
                    matrix = mathutils.Matrix(get.matrix())
                    x,y,z = matrix[3][0],matrix[3][1],matrix[3][2]

                    # Rename model vertex groups to correct names
                    if(ob!='' and str(boneId) in ob.vertex_groups):
                        ob.vertex_groups[str(boneId)].name = name

                    if(debug): # Not finished, only in debug mode
                        # Add armature bones
                        bone = arm_ob.data.edit_bones.new(name=name)
                        bone.head = (x, y, z) # move the head/tail to keep the bone
                        bone.tail = (x, y, z-0.1)
                        #bone.id_data.transform(matrix)
                        #bone.transform(matrix)
                        # Constraint bone to mesh cube with same name 
                        if(name in bpy.data.objects and edit_mode and imp_anim):
                            bpy.ops.object.mode_set(mode='OBJECT')
                            #c = arm_ob.pose.bones[name].constraints.new('COPY_LOCATION')
                            c = arm_ob.pose.bones[name].constraints.new('COPY_TRANSFORMS')
                            c.target = bpy.data.objects[name]
                            bpy.ops.object.mode_set(mode='EDIT', toggle=False)

                    # Keyframe animation
                    get.checkHeader('kfra')
                    get.i() # version
                    numKfra = get.i() # Number of keyframes
                    for y in range(0, numKfra):
                        rot = get.f(), get.f(), get.f(), get.f()
                        loc = get.f(), get.f(), get.f() #X Z Y
                        timeS = get.f() # Seconds
                        #frame = timeS*render_fps
                        #if(not ob==''):
                        #    #ob.rotation_euler = rot[0], rot[2], rot[1]
                        #    ob.rotation_mode = 'QUATERNION'
                        #    ob.rotation_quaternion = rot[3], rot[0]*-1, rot[2]*-1, rot[1]*-1  #wxyz blender, xzyw wreckfest
                        #    ob.location = loc[0], loc[2], loc[1]
                        #    ob.keyframe_insert(data_path="location", frame=frame)
                        #    ob.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            if(ob!='' and '0' in ob.vertex_groups): # Delete unused default vertex group
                ob.vertex_groups.remove(ob.vertex_groups['0'])
            if(edit_mode): # Exit edit mode
                bpy.ops.object.mode_set(mode='OBJECT')

        get.skipToHeader('dmmy') 
        get.i() # version
        numdummy = get.i()
        for x in range(0, numdummy):
            dmmymx = mathutils.Matrix(get.matrix())
            rootmx = mathutils.Matrix(matrix)
            rootmx.transpose() # flip colums and rows
            dmmymx.transpose()
            dmmymx = rootmx @ dmmymx # matrix multiplication to use both matrixes in object
            dmmyname = get.wftext()
            dmmyob = bpy.data.objects.new( dmmyname, None )
            link_to_collection(dmmyob, 'Models-Dummies')
            dmmyob.empty_display_size = 0.03
            dmmyob.matrix_world = dmmymx
            dmmyob.show_name = True
            bpy.context.view_layer.objects.active = dmmyob
            dmmyob.select_set(True)
        get.skip(4*3)

        if(ob==''): # If no object exist yet / Create simple box for collision only models
            ob = create_cube_ob(modelname, size=1.0, collection="Models-collision", meshname=modelname)
            ob.matrix_world = matrix

        # setting collisions / dynamics
        if(DynamicTypeString != "static"):
            ob['CustomData'] = 'dyn = "'+DynamicTypeString+'"'
        elif(numShapes > 0 and numBaseMesh == 0):
            ob['CustomData'] = 'vis = false | col = true' 
        elif(numShapes > 0):
            ob['CustomData'] = 'col = true'
        elif(numBaseMesh == 0):
            ob['CustomData'] = 'vis = false'
        
    wm.progress_end()
 

def make_models_placeholder(get,filepath,short_pth,use_color=0, model_upd=False, model_onlyupd=False):
    '''MODELS import. Combine all into one placeholder object'''
    mdl_version = get.i() # version: rru 0, wf 5
    nummdl = get.i() # number of models
    print ("\nFound",nummdl,"Models")
    #if(nummdl==0): return

    # Getting the full #xref path after /data/ 
    filepath = to_wf_path(filepath)   

    verts, triangles, uvs, allverts, alltriangles, alluvs = [], [], [], [], [], []
    voffset = 0
    allvoffset = 0

    for x in range(0, nummdl):
        modelname = get.wftext()
        DynamicTypeString = get.wftext()
        if(str(chr(163)) in DynamicTypeString): return None
        if(mdl_version>0): # wf
            get.text(4)
            get.wftext()
        matrix = get.matrix()
        get.skip(4*6) # cx cz...

        get.checkHeader('pmsh')
        detailed_import = True
        if(detailed_import):
            triangles = [] # fix for models without visible mesh
            verts = []
            get.i() #1 version
            numBaseMesh = get.i()
            for y in range(0, numBaseMesh):
                cx2, cz2, cy2 = get.f(), get.f(), get.f()
                ex2, ez2, ey2 = get.f()*2, get.f()*2, get.f()*2 

                if(get.checkHeader('mesh')):
                    get.i() #0 version
                    numMesh = get.i()
                    for zz in range(0, numMesh):
                        meshName = get.wftext()

                        get.checkHeader('btch')
                        get.i() #2 version
                        numBatch = get.i()
                        verts = []
                        triangles = []
                        uvs = []
                        voffset = allvoffset
                        for yy in range(0, numBatch):
                            biasX, biasZ, biasY, biasW = get.f(), get.f(), get.f(), get.f()
                            minX, minZ, minY = get.f(), get.f(), get.f() # BBox Min
                            maxX, maxZ, maxY = get.f(), get.f(), get.f() # BBox Max

                            get.checkHeader('mtrl')

                            get.skipToHeader('vert')
                            version = get.i() # version: rru 3, wf 4
                            numVert = get.i()
                            newVersion = version > 3
                            e = get.endian # rru big endian, wf little endian
                            if(newVersion): # new wf format
                                # Numpy is fastest way to interpret bytes
                                rawdata = get.readBytes(32*numVert) # Vert data = 32 bytes
                                dtype = np.dtype([
                                ("x", e+"i2"),
                                ("z", e+"i2"),
                                ("y", e+"i2"),
                                ("w", e+"i2"),
                                ("n", e+"i4"),
                                ("uvx", e+"i2"),
                                ("uvy", e+"i2"),
                                ("n2", e+"i4"),
                                ("uvx2", e+"i2"),
                                ("uvy2", e+"i2"),
                                ("bindex", ">i2"),
                                ("bindex2", ">i2"),
                                ("bweight", ">i2"),
                                ("bweight2", ">i2"),
                                ])
                                for vert in np.frombuffer(rawdata, dtype=dtype, count=-1).tolist():
                                    x, z, y, w, n, uvx, uvy, n2, uvx2, uvy2, bindex, bindex2, bweight, bweight2 = vert
                                    x, y, z = x*biasW+biasX, y*biasW+biasY, z*biasW+biasZ
                                    x, y, z = apply_matrix((x,y,z), matrix)
                                    verts.append((x, y, z))
                                    uvs.append((uvx, uvy))
                            else: # rru / old wf
                                for v in range(0, numVert):
                                    x, z, y, w, n, uvx, uvy = get.read('hhhhihh') # h = signed short int (2bytes)
                                    x, y, z = x*biasW+biasX, y*biasW+biasY, z*biasW+biasZ
                                    x, y, z = apply_matrix((x,y,z), matrix)
                                    verts.append((x, y, z))
                                    uvs.append((uvx, uvy))

                            get.checkHeader('tria')
                            get.i() # version
                            numTri = get.i()
                            # Numpy is fastest way to interpret bytes
                            rawdata = get.readBytes(6*numTri) # Tri data = 6 bytes
                            dtype = np.dtype([
                                ("a", e+"u2"),    
                                ("c", e+"u2"),
                                ("b", e+"u2"),
                                ])
                            for tri in np.frombuffer(rawdata, dtype=dtype, count=-1).tolist():
                                a, c, b = tri
                                triangles.append((a+voffset,b+voffset,c+voffset))
                                #triMatIdlist.append(currentMatId)
                            voffset = voffset + numVert


                            get.checkHeader('edgm')
                            get.i() # version
                            for v in range(0, get.i()):
                                get.wfdata()
                                get.wfdata()
                                get.wfdata()
                                get.wfdata()

        get.skipToHeader('shpe')
        get.i() # version
        numShapes = get.i() # Number of Shapes

        get.skipToHeader('anim')

        get.skipToHeader('dmmy') 
        get.i() # version
        numdummy = get.i()
        for x in range(0, numdummy):
            get.matrix()
            get.wftext()
        get.skip(4*3)
    
        if(not '$p' in modelname): # Merge files to placeholder, except part files
            allverts += verts
            alltriangles += triangles
            alluvs += uvs
            allvoffset = voffset


    hash = hashy(filepath) # Generating hash used as model geometry datablock name

    if(model_onlyupd or model_upd): # Updating existing geometry
         if(bpy.data.meshes.get(hash) is not None and len(alltriangles)>0):

            # Store new placeholder into temporary mesh
            tmpmesh = bpy.data.meshes.new("tmpmesh")
            tmpmesh = from_pydata_safe(tmpmesh, allverts, [], alltriangles)

            # Replace old placeholder with the new mesh
            mesh = bmesh.new()
            mesh.from_mesh(tmpmesh)
            mesh.to_mesh(bpy.data.meshes[hash])
            mesh.free()

            # Wip
            try:
                uv.uv(bpy.data.meshes[hash],alluvs)
            except NameError:
                pass

            # Delete temporary mesh
            bpy.data.meshes.remove(tmpmesh)
            #mesh.update() # To ensure viewport update in Blender 2.8
            newmaterial = 0
            
    if (model_onlyupd==False): # Making new object
        if (bpy.data.meshes.get(hash) is not None): 
            # Use existing mesh from Blender
            mesh = bpy.data.meshes[hash]
            newmaterial = 0
        else:
            # Create an empty mesh and place data    
            mesh = bpy.data.meshes.new(hash)

            if len(allverts)>2: # Get model
                mesh = from_pydata_safe(mesh, allverts, [], alltriangles)
            else:
                # Create cube
                bm = bmesh.new()
                bmesh.ops.create_cube(bm, size=1.0)
                bm.to_mesh(mesh)
                bm.free()

            newmaterial = 1

        # Create the object
        name = filepath
        if(short_pth): name = shorthand_path(name,filepath)
        ob = bpy.data.objects.new("#xref"+" "+name, mesh)
        
        # Random color
        if(newmaterial and use_color):
            mat = bpy.data.materials.new('Z')
            mat.diffuse_color = text_to_color(filepath)
            ob.active_material = mat    

        # Add the object into the scene.
        link_to_collection(ob, "Subscenes")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True) 


def make_lights(get):
    '''LIGHTS import'''
    get.i() # version
    num = get.i() # number of lights
    if(num>0): print ("Found",num,"Lights")
    for x in range(0, num):
        mx = get.matrix()
        name = get.wftext()
        color = get.read('fff') 
        intensity, atStart, atEnd, hotspotsize = get.read('ffff')
        aspect, overshoot, ltype, group = get.read('fihh')
        light_type = 'SPOT' if ltype == 1 else 'POINT'
        name = 'Light' if name == '' else name
        ob = create_light_ob(name, light_type, color=color, power=intensity, collection='Lights')
        ob.data.use_custom_distance = True
        ob.data.cutoff_distance = atEnd
        if light_type == 'SPOT':
            ob.data.spot_size = hotspotsize / 180 * math.pi # radians
        else:
            ob.data.shadow_soft_size = hotspotsize
        ob.matrix_world = mx

def locate_subscene(filepath,scne_relpath):
    filepath = filepath.replace('\\', '/')
    # Checking under common /data/ folder
    path = re.split("/data/", filepath)[0] # keep everything before /data/
    path += "/" + scne_relpath
    if os.path.isfile(path):
        return path
    # Checking under common /Wreckfest/data/
    if "/Wreckfest/" in filepath:
        path = re.split("/Wreckfest/", filepath)[0] # keep everything before /Wreckfest/
        path += "/Wreckfest/" + scne_relpath
        if os.path.isfile(path):
            return path
    # Checking under Wreckfest/data/ located by toolbox preferences
    try:
        path = bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path + scne_relpath
    except:
        pass
    if os.path.isfile(path):
        return path
        
def make_subscenes(get,short_pth=0,use_color=1,imp_subscn_mdl=0,filepath=''):
    '''SUBSCENES import'''
    scne_version = get.i() # version, latest=3
    numscenes = get.i() # number of subscenes
    print ("Found",numscenes,"Subscenes")
    
    wm = bpy.context.window_manager
    wm.progress_begin(0, numscenes) # load indicator
    
    for x in range(0, numscenes):
        mx = get.matrix() # matrix
        if(scne_version >= 3): # scale
            scalex = get.f()
            scaley = get.f()
            scalez = get.f()
            if(scalex==0): scalex=1 # rewrite incorrect scale
            if(scaley==0): scaley=1
            if(scalez==0): scalez=1
        heading = get.i() # Heading 0=Both? 1=forward? 2=backward?
        flags = get.i() # Flags-Start 1=yes?
        name = get.wftext() # name (#ai_route#xref...)
        scne_relpath = ""
        if(get.checkHeader('scne')):
            scne_relpath = get.wftext()
        scne_name = scne_relpath
        # Generating hash and random color from path + file name
        hash = hashy(scne_name)
        color = text_to_color(scne_name)
        
        if(short_pth): # shortening paths
            scne_name = shorthand_path(scne_name,filepath)

        if (bpy.data.meshes.get(hash) is not None):
            # Use existing mesh from Blender
            mesh = bpy.data.meshes[hash]
            newmaterial = 0
            new_mesh_made = False
        else:
            # Create an empty mesh 
            mesh = bpy.data.meshes.new(hash)
            # Transform matrix to move origin to bottom of cube
            moveUp = mathutils.Matrix.Translation((0.0, 0.0, 1.0))
            # Construct the bmesh cube and assign it to the blender mesh.
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=2.0, matrix=moveUp)
            bm.to_mesh(mesh)
            bm.free()
            newmaterial = 1
            new_mesh_made = True
            
        # Hack original numbering from name
        num = name.split('#xref')[-1] # get part after #xref text
        num = num.replace(scne_name.split('/')[-1], '') # remove file-name if it is in name field
        num = ''.join(i for i in num if i.isdigit()) # leave only numerals
        if(len(num)>0): num = '.'+num
        
        # Create the object
        o = bpy.data.objects.new("#xref "+scne_name+num, mesh)

        # Check if path fits in placeholder name
        if(len(scne_name)>53):
            o['xdir'] = scne_relpath.rsplit('/',maxsplit=1)[0]+'/' # Store too long path in custom property
            o.name = "#xref "+scne_name.rsplit('/',maxsplit=1)[-1]+num # Remove path from object name
        
        # Store original name, heading, flags in custom properties
        #o['Name'] = name
        if(heading != 0): o['Heading'] = heading
        if(flags != 0):o['Flags'] = flags
         
        # Add the object into the scene.
        link_to_collection(o, "Subscenes")
        o.matrix_world = mx  
        if(scne_version >= 3): o.scale = (scalex,scalez,scaley) # scale object
        bpy.context.view_layer.objects.active = o
        o.select_set(True)

        if(newmaterial and use_color):
            mat = bpy.data.materials.new('Z')
            mat.diffuse_color = color
            #o = bpy.context.selected_objects[0] 
            o.active_material = mat

        # Importing placeholder model
        if(new_mesh_made and imp_subscn_mdl):
            path = locate_subscene(filepath, scne_relpath)
            if(path is not None):
                read_scne('', (path), short_pth, use_color, imp_model=True, placeholder_mode=True, model_onlyupd=True)

            
        if(x%10==0): wm.progress_update(x) # load indicator update every 10th subscene
        
    wm.progress_end()
    
def make_antiportals(get):
    '''ANTIPORTALS import'''
    get.i() # version
    num = get.i()
    print ("Found",num,"Antiportals")
    for y in range(0, num):
        zeroplane = get.i() # Zero For Plane
        verts = []
        for i in range(0, 8):
            x, z, y = get.f(), get.f(), get.f()
            verts += [x,y,z],
        faces = ((2,3,4,5),(1,0,7,6),(6,7,3,2),(7,0,4,3),(2,5,1,6),(5,4,0,1)) # L,R,Face,Bottom,Top,Back
        create_mesh_ob("#antiportal", verts, faces, meshname='antiportal', collection='Antiportals')

def make_airoutes(get,debug=False):
    '''AIROUTES import'''
    def flip_yz(x, y, z):
        return x, z, y
    def perc(percentage, x1, x2): # Calculates point between x1 and x2
        return (x1+((x2-x1)*percentage))
    def route_position(percentage, L, R): # Calculates sector coordinates from percentage between Left and Right border
        return perc(percentage,L[0],R[0]), perc(percentage,L[1],R[1]), perc(percentage,L[2],R[2])
    def expand_vert(vert, prevVert, distance):
        x, y, z = vert 
        deltaX = x - prevVert[0]
        deltaY = y - prevVert[1]
        angleRadians = math.atan2(deltaY, deltaX)
        newX = x + distance * math.cos(angleRadians)
        newY = y + distance * math.sin(angleRadians)
        return newX, newY, z
    def expand_route(route, dist):
        route[0] = expand_vert(route[0],route[2],dist) # Expand first sector
        route[1] = expand_vert(route[1],route[3],dist)
        route[-1] = expand_vert(route[-1],route[-3],dist) # Expand last sector
        route[-2] = expand_vert(route[-2],route[-4],dist)
        return route

    version = get.i() # version: WF1=0, WF2=1
    WF2 = (version>0)
    num = get.i() # number of airoutes (1=if not alt routes)
    print ("Found",num,"Airoutes")
    for route in range(0, num):
        get.checkHeader('aisc')
        get.i() # version
        numsec = get.i() # number of aisectors
        
        faces = []
        verts = []
        vertsRace = []
        vertsSafe = []
        count = 0
        
        for s in range(0, numsec):
            count += 2
            if(s != 0): # skipping first sector
                faces += (count-1, count-2, count-4, count-3), # make face between previous and current sector 

            L = flip_yz(get.f(), get.f(), get.f()) # Blue Border sector x,y,z
            R = flip_yz(get.f(), get.f(), get.f())
            LSafe = route_position(get.f(), L, R) # Safe Line sector x,y,z
            if(WF2): u1 = get.f()
            RSafe = route_position(get.f(), L, R) 
            if(WF2): u2 = get.f()
            LRace = route_position(get.f(), L, R) # Race Line sector x,y,z
            if(WF2): u3 = get.f()
            RRace = route_position(get.f(), L, R)
            if(WF2): u4 = get.f()

            verts += L, R,
            vertsSafe += LSafe, RSafe,
            vertsRace += LRace, RRace,

            if(debug):
                label = create_empty_ob(str(s)+'  ('+str(route)+')', type='SINGLE_ARROW', collection='Airoute '+str(route)+' Sectors')
                label.location = L
                label.show_name = True
                label.show_in_front = True

            if(WF2):
                u5 = get.i()

        startIdMainrt = get.i() # Start Index Of Mainroute Sector
        endIdMainrt = get.i() # End Index Of mainroute sector
        get.wftext() # Custom property, empty.

        if(WF2):
            unknown = get.i(), get.f(), get.i(), get.f(), get.i(), get.i(), get.i(), get.i(), get.i(), get.i(), get.i()
            
        vertsSafe = expand_route(vertsSafe, dist=0.25)
        vertsRace = expand_route(vertsRace, dist=0.5)

        if(route==0): ending = "main"
        else: ending = "alt"+str(route)
        

        ai_route_ob = create_mesh_ob("#ai_route_"+ending, verts, faces, meshname="route", show_wire=True, color=(0, 0, 1, 0.03), colorname="blue-route", collection="Airoutes", use_nodes=True)
        ai_route_ob.color = (0,0,1, 1) # Object color
        ai_safe_ob = create_mesh_ob("#ai_safe_"+ending, vertsSafe, faces, meshname="route", show_wire=True, color=(1, 0, 0, 0.15), colorname="red-route", collection="Airoutes", use_nodes=True)
        ai_safe_ob.color = (1,0,0, 1)
        ai_race_ob = create_mesh_ob("#ai_race_"+ending, vertsRace, faces, meshname="route", show_wire=True, color=(0, 0.8, 0.05, 1), colorname="green-route", collection="Airoutes", use_nodes=True)
        ai_race_ob.color = (0,1,0, 1)
        
        firstRightBorderVert = verts[1] # StartZ, Normally least negative / largest Y value
        lastLeftBorderVert = verts[-2]
        if(route==0): # First route = main route
            if(firstRightBorderVert[1] > lastLeftBorderVert[1]): # Comparing Y (In Bagedit Z) value of route verts
                ai_route_ob['CustomData'] = 'otherway = true'
        else: # Alt Route
            if(startIdMainrt > endIdMainrt):
                ai_route_ob['CustomData'] = 'crossstart = true'

def make_startpoints(get):
    '''STARTPOINTS import'''
    get.i() # version
    num = get.i() # number of startpoints
    print ("Found",num,"Startpoints")
    for x in range(0, num):
        name = get.wftext()
        mx = get.matrix()
        ob = create_empty_ob(name, 'CUBE', size=0.5, collection='Startpoints') # 1m x 1m x 1m size
        ob.matrix_world = mx
        ob.scale = (2, 5, 1) # car placeholder 2m x 5m x 1m
  
def make_checkpoints(get):
    '''CHECKPOINTS import'''
    version = get.i() # version
    num = get.i() # number of Checkpoints
    print ("Found",num,"Checkpoints")
    for cp in range(0, num):
        isSplit = get.i(1) # Is Split Point (1byte > 0-127)
        rtIndex = get.i(1) # Route Index
        altRoutePrx = get.i(1) # Alt Route Proxy For Main Route Checkpoint Index, Default (-1)
        middleX, middleZ, middleY = get.f(), get.f(), get.f()
        LX, LZ, LY = get.f(), get.f(), get.f()
        RX, RZ, RY = get.f(), get.f(), get.f()
        unknown=0
        if version >= 5: #WF2
            unknown = get.i(4)
        cpname = "#checkpoint"
        cpname += "{0:0>2}".format(cp+1)
        if(isSplit>0): cpname += "_split"
        if(rtIndex>0): cpname += "_alt"+str(rtIndex)
        if(altRoutePrx>-1): cpname += "_proxy"+str(altRoutePrx)
        if(unknown>0): cpname += "_???"+str(unknown)

        if(version>3):
            verts = ((LX,LY,LZ+5), (RX,RY,RZ+5), (RX,RY,(RZ-5)), (LX,LY,(LZ-5)))
        else:
            verts = ((LX,LY,LZ), (RX,RY,RZ), (RX,RY,(RZ-10)), (LX,LY,(LZ-10)))

        faces = ((0,1,2,3),)
        create_mesh_ob(cpname,verts,faces,"checkpoint", collection="Checkpoints", show_wire=True)

def make_volumes(get):
    '''VOLUMES import'''
    version = get.i() # version
    num = get.i() # number of volumes
    print ("Found",num,"Trigger Volumes")
    for x in range(0, num):
        matrix = get.matrix()
        aabb = get.f(), get.f(), get.f(), get.f(), get.f(), get.f()
        cx, cz, cy, ex, ez, ey = aabb
        name = get.wftext()

        get.checkHeader('tvpl')
        get.i() # version
        for x in range(get.i()): # 6 times
            get.skip(4*4)
        
        vol = ''
        if(version>1): # Settings / reference to .tvls file  
            get.checkHeader('tvls')
            vol = get.wftext()
        
        mx = mathutils.Matrix.Translation((cx, cy, cz))
        mx = mx @ mathutils.Matrix.Scale(ex*2, 4, (1.0, 0.0, 0.0))
        mx = mx @ mathutils.Matrix.Scale(ey*2, 4, (0.0, 1.0, 0.0))
        mx = mx @ mathutils.Matrix.Scale(ez*2, 4, (0.0, 0.0, 1.0))

        o = create_cube_ob(name, size=1.0, collection="Trigger Volumes", matrix=mx) # Apply mx matrix to cube
        o.matrix_world = matrix # set transformation

        if(vol!=''): o['CustomData'] = 'vol = "'+vol+'"'

def make_prefabs(get):
    '''PREFABS import'''
    version = get.i() # version
    num = get.i() # number of prefabs
    print ("Found",num,"Prefabs")
    for x in range(0, num):
        get.checkHeader("prfb")
        name = get.wftext()
        if(name.endswith(".prfb")): # to shorthand format
            name = name[:-5].replace("data/property/prefab/", "")
        o = create_cube_ob( '!'+name+'!' , size=1.0, collection="Prefabs")
        bpy.context.view_layer.objects.active = o
        o.select_set(True)

def make_vhcl_dummies(get):
    '''VEHICLE DUMMIES import'''
    get.i() # version
    for x in range(get.i()):
        matrix = get.matrix()
        name = get.wftext()
        o = bpy.data.objects.new( name, None )
        if('light' in name.lower()):
            link_to_collection(o, 'Dummies-Light')
        elif('emitter' in name.lower()):
            link_to_collection(o, 'Dummies-Emitter')
            o.empty_display_type = 'CONE'
        else:
            link_to_collection(o, 'Dummies')
        o.empty_display_size = 0.03
        o.matrix_world = matrix
        o.show_name = True
        bpy.context.view_layer.objects.active = o
        o.select_set(True)

def make_vhcl_spheres(get):
    '''VEHICLE SPHERES import'''
    get.i() # version
    mesh = bpy.data.meshes.new("collision_sphere")
    bm = bmesh.new()
    if (bpy.app.version>=(3,0)): # Blender 3.0 and above
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1)
    else: # Here diameter param sets actually radius.
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, diameter=1)
    for f in bm.faces: f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    for x in range(get.i()):
        name = get.wftext()
        x, z, y = get.f(), get.f(), get.f()
        radius = get.f()
        o = bpy.data.objects.new( name, mesh )
        link_to_collection(o, 'Spheres')
        o.location.x = x
        o.location.y = y
        o.location.z = z
        radius=radius
        o.scale = (radius,radius,radius)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        o['CustomData'] = 'IsCollisionModel = true'

def make_minmax_boxes(get, collection, customdata):
    '''Read 6 coordinates and import as cube'''
    get.i() # version
    for x in range(get.i()):
        name = get.wftext()
        minx, minz, miny = get.f(), get.f(), get.f()
        maxx, maxz, maxy = get.f(), get.f(), get.f()
        o = create_cube_ob(name, size=1.0, collection=collection)
        o.scale.x = abs(minx-maxx) # width
        o.scale.y = abs(miny-maxy)
        o.scale.z = abs(minz-maxz)  
        o.location.x = (maxx+minx)/2 # average = middle point = coordinate
        o.location.y = (maxy+miny)/2
        o.location.z = (maxz+minz)/2
        if(customdata!=''): o['CustomData'] = customdata

def make_vhcl_proxies(get):
    '''VEHICLE PROXIES import'''
    make_minmax_boxes(get, collection='Proxies', customdata='IsCollisionModel = true')



def flipVerts(rawVerts):
    '''Flip Z and Y coordinates in vertex list'''
    verts = []
    for v in rawVerts: 
        verts += (v[0],v[2],v[1]),
    return verts

def read_section(get,header,dataformat):
    '''Read headers and all blocks of section using #struct unpack dataformat'''
    get.checkHeader(header)
    get.i() #version
    data = []
    for x in range(get.i()):
        data += (get.read(dataformat)),
    return data

def make_vhcl_deform(get):
    '''VEHICLE DEFORM import'''
    # Data reading #
    # Collision Nodes
    verts = flipVerts(read_section(get,'vect','ffff')) #X,Y,Z,W    #f = float
    # Collision Distance Constraints
    edges = read_section(get,'line','HH') #A,B    #H = unsigned short int (2bytes)
    # Collision Altitude Constraints  
    faces = read_section(get,'tetr','HHHH') #A,B,C,D 
    # Collision Shape Positions
    ColShapes = flipVerts(read_section(get,'vect','ffff')) #X,Y,Z,W
    # Collision Shape radius
    ColShapeRadius = get.f()

    # Collision Nodes Model
    for v in verts:
        o = create_cube_ob("Deform_node", size=0.02, collection="Deform Nodes")
        o.location.x, o.location.y, o.location.z = v

    # Collision Distance Constraints Model
    if(len(edges)>0):
        mesh = bpy.data.meshes.new("Distance_constraints")
        mesh.from_pydata(verts, edges, [])
        o = bpy.data.objects.new("Distance_constraints", mesh)
        link_to_collection(o, 'Deform Distance Constraints')
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        o.color = (1,0,0, 1)

    ### Collision Shape Positions Model
    mesh = bpy.data.meshes.new("Col_shape_position")
    bm = bmesh.new()
    if (bpy.app.version>=(3,0)): #Blender 3.0 and above
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=ColShapeRadius/2)
    else: #Here diameter param sets actually radius
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, diameter=ColShapeRadius/2)
    for f in bm.faces: f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    for val in ColShapes:
        o = bpy.data.objects.new("Col_Shape_Position", mesh )
        link_to_collection(o, 'Deform Collision Shape Positions')
        o.location = val[0], val[1], val[2]
        o.display_type = 'WIRE'
        o.show_in_front = True

    # Altitude constraints Model
    for v in faces:
        mesh = bpy.data.meshes.new("Altitude_constraint")
        face = [(v[0],v[1],v[2]), (v[0],v[1],v[3]), (v[0],v[2],v[3]), (v[1],v[2],v[3]),]
        mesh.from_pydata(verts, [], face)

        o = bpy.data.objects.new("Altitude_constraint", mesh)
        link_to_collection(o, 'Deform Altitude Constraints')
        bpy.context.view_layer.objects.active = o
        o.select_set(True)


def make_vhcl_boxes(get):
    '''VEHICLE/VHCM import'''
    get.skipToHeader('vbox') # Top Box
    make_minmax_boxes(get, collection='Vhcm', customdata='IsCollisionModel = true')
    get.skipToHeader('vbox') # Bottom Box
    make_minmax_boxes(get, collection='Vhcm', customdata='IsCollisionModel = true')

def create_fallback_model(filepath):
    '''Fallback cube for encrypted files'''
    filename = os.path.basename(filepath).lower()
    if filename.endswith('.vhcl') and filename != 'body.vhcl':
        name = filename.split('.')[0]
        name = re.sub(r'_(\d+)$', r'#part\1', name)

        create_cube_ob(name, size=1.0, collection='Encrypted-failed-import')


def breckfest_uncompress(filepath):
    '''Uncompress and return data of .scne file'''
    breckfest_location = breckfest_locate()  
    args = [breckfest_location, '-dump', filepath]
    if sys.platform != 'win32':  args = [config.wine_cmd] + args # In Linux run .exe with wine
    print("\n"+' '.join(args))
    if not os.path.isfile(breckfest_location): 
        popup("Breckfest.exe not found. Check paths in addon preferences.")
        return None
    try: subprocess.run(args) # Uncompress with Breckfest (run = wait for Breckfest to finish)
    except OSError:
        popup("Unable to run Breckfest.exe. Move Breckfest to location with enough permissions. Check paths in addon preferences.")
        return None
    if os.path.isfile(filepath+".raw"):
        with open(filepath+".raw", 'rb') as f:
            file = f.read()
        os.remove(filepath+".raw") # remove file .scne.raw created by Breckfest
        return file
    else: # Breckfest failed to uncompress:
        with open(filepath, 'rb') as f: header = f.read(4)
        if (header == b'\x08\x00\x00\x00'): popup('ERROR: File is encrypted! \n '+filepath)
        elif (header == b'\x07\x00\x00\x00'): popup('ERROR: WF2 file must be decompressed with Bag-decompress first! \n '+filepath)
        elif (header == b'\x0A\x00\x00\x00'): popup('ERROR: WF2 file must be decompressed with Bag-decompress first! \n '+filepath)
        elif (os.path.getsize(filepath)>6590000): popup('Breckfest uncompress failed. Possibly too large filesize. \n '+filepath)
        else: popup('Breckfest uncompress failed! \n '+str(filepath))
        create_fallback_model(filepath)

def autolink_node(node_tree, node_to_link):
    '''Automatically link texture to inputs in #pbr shader node'''
    input_map = {'c': 1, 'c1': 1, 'c5': 1, 'ao': 7, 'n': 8, 's': 9}
    suffix = os.path.splitext(node_to_link.image.name)[0].rsplit('_',maxsplit=1)[-1]
    if suffix in input_map:
        # Find #pbr node
        pbrNode = None
        for node in node_tree.nodes:
            if node.type=='GROUP' and '#pbr' in node.node_tree.name:
                pbrNode = node
                break
        # Link
        if pbrNode:
            node_tree.links.new(pbrNode.inputs[input_map[suffix]], node_to_link.outputs['Color'])

            if suffix in ['c1', 'c5']:
                 node_tree.links.new(pbrNode.inputs[13], node_to_link.outputs['Alpha'])

def import_bmap(context, filepath):
    print("Importing Bmap from ",filepath)

    filepath = filepath.replace('/','\\')
    fileName = filepath.split('\\')[-1]

    # Path of webp file in Bmap Cache
    wf_path = bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path
    relpath = "data\\" + re.split(r'\\data\\', filepath)[-1] # remove everything before /data/
    bmapcache_path = os.path.join(wf_path, 'tools', 'BmapCache', relpath[:-5] + '.' + config.c_extension) # Bmap cache in Wreckfest/tools/BmapCache

    mat = bpy.context.active_object.active_material

    # Count existing image nodes
    number_of_nodes = 0
    for node in mat.node_tree.nodes:
        if node.type=='TEX_IMAGE':
            number_of_nodes += 1

    # Create image node
    imageNode = mat.node_tree.nodes.new('ShaderNodeTexImage')
    imageNode.hide = True # Collapse node
    nodeXLocation = -300 - math.floor(number_of_nodes/10) * 250 # New colums each 10 nodes 250 on left
    nodeYLocation = 250 - (number_of_nodes%10) * (50 if number_of_nodes<10 else 40)
    imageNode.location = (nodeXLocation,nodeYLocation)
    mat.node_tree.nodes.active = imageNode

    # Add image to node
    pngfile = filepath[:-5] + '.png'
    tgafile = filepath[:-5] + '.tga'
    in_mods = '\\mods\\' in filepath 
    if in_mods and os.path.isfile(pngfile): # Use existing png if available
        imageNode.image = image_refer(fileName[:-5]+'.png', fullPath=pngfile)
    elif in_mods and os.path.isfile(tgafile): # Use existing tga if available
        imageNode.image = image_refer(fileName[:-5]+'.tga', fullPath=tgafile)
    elif (fileName in bpy.data.images and bpy.data.images[fileName].filepath == bmapcache_path): # Use existing image from Blender if available
        imageNode.image = bpy.data.images.get(fileName) 
    else: # Make new image

        # Convert and save webp file on disk
        convert_bmap_file_to_image( bmapFile=filepath, tgaPath=bmapcache_path, quality=90, resolution=config.c_resolution, file_format='WEBP')

        # Link in Shader Node image datablock
        imageNode.image = image_refer(fileName, fullPath=bmapcache_path)

    autolink_node(node_tree=mat.node_tree, node_to_link=imageNode) 


def read_scne(context, filepath, short_pth=False, use_color=False, imp_model=False, imp_shpe=False, imp_anim=False, imp_mat=False, placeholder_mode=False,
    model_upd=False, model_onlyupd=False, imp_subscn=False, imp_subscn_mdl=False, imp_portal=False, imp_airt=False, imp_startpt=False, imp_cp=False,
    imp_vol=False, imp_pfb=False, imp_tga=False, use_wftb=False, debug=False, directory=''):
    '''SCNE, VHCM and VHCL file import'''
         
    print ("\n\nImporting from:",filepath)

    if(filepath.split('//')[-1] == ''): return {'FINISHED'} # not file selected
    if(model_onlyupd and bpy.data.meshes.get(hashy(to_wf_path(filepath))) is None): return {'FINISHED'} # not mesh update to missing models

    with open(filepath, 'rb') as f:
        # Check file header
        header = f.read(4)
        f.seek(0)
        format01 = (header==b'\x01\x00\x00\x00')
        rruFormat = (header==b'scne' or header==b'vhcl')
        uncompressed = (filepath[-4:]==".raw" or rruFormat or format01)
        # Uncompressed file
        if uncompressed:
            get = BagParse(f.read()) 
            if format01: get.skip(12) # Skip lz4 header
            if rruFormat: get.endian = '>' # Change endianess
    # Compressed file
    if not uncompressed: 
        get = BagParse(breckfest_uncompress(filepath)) 


    

    # Quit if data not found
    if(not get.bytes): return {'FINISHED'}

    # Load shaders
    NodeGroupShader.reset()
    if use_wftb:
        NodeGroupShader.load()

    # Increase frame rate for animation imports
    #if(imp_anim and bpy.context.scene.render.fps==24):
    #    bpy.context.scene.render.fps = 60
        

    if(filepath[-5:] == ".vhcl"): # VHCL-format
        get.skipToHeader('modl') 
        make_models(get, filepath, short_pth, imp_anim, imp_mat, imp_tga, debug, imp_shpe=imp_shpe)
        get.skipToHeader('dmmy')
        make_vhcl_dummies(get)
        get.skipToHeader('vsph')
        make_vhcl_spheres(get)
        get.skipToHeader('vbox')
        make_vhcl_proxies(get)
        if(debug): make_vhcl_deform(get)

    elif(filepath[-5:] == ".vhcm"): # VHCM-format
        make_vhcl_boxes(get)
        
    else: # SCNE-format

        # Subscene placeholder
        if(placeholder_mode):
            get.skipToHeader('modl')
            make_models_placeholder(get, filepath, short_pth, use_color, model_upd, model_onlyupd)

        else: # Normal import
            if rruFormat: imp_startpt, imp_cp = False, False
            get.skipToHeader('modl')
            if(imp_model): make_models(get, filepath, short_pth, imp_anim, imp_mat, imp_tga, debug, imp_shpe=imp_shpe)
            get.skipToHeader('ltpd') 
            make_lights(get)
            get.skipToHeader('ssce') 
            if(imp_subscn): make_subscenes(get, short_pth, use_color, imp_subscn_mdl, filepath)
            get.skipToHeader('aprl') 
            if(imp_portal): make_antiportals(get)
            get.skipToHeader('airt')
            if(imp_airt): make_airoutes(get, debug)
            get.skipToHeader('trsp')
            if(imp_startpt): make_startpoints(get)
            get.skipToHeader('trcp')
            if(imp_cp): make_checkpoints(get)
            get.skipToHeader('tvlm')
            if(imp_vol): make_volumes(get)
            if(not rruFormat):
                get.skipToHeader('scpf')
                if(imp_pfb): make_prefabs(get)

    # Increase screen clipping distance
    for a in bpy.context.screen.areas:
        if a.type == 'VIEW_3D':
            break
    if(a.spaces.active.clip_end == 1000):
        a.spaces.active.clip_end = 8000

        
    return {'FINISHED'}
