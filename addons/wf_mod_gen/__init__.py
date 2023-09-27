# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons CC0
# https://creativecommons.org/publicdomain/zero/1.0/
#
# ##### END LICENSE BLOCK #####

bl_info = {  
    "name": "Wreckfest Mod Generator",  
    "author": "Mazay",  
    "version": (0, 6),  
    "blender": (2, 80, 0),  
    "location": "File > New > Wreckfest",  
    "description": "",  
    "warning": "",  
    "doc_url": "https://github.com/gmazy/wreckfest_toolbox/wiki",  
    "tracker_url": "", 
    "category": "Interface"}  



import bpy
import os
import re
import shutil
from . import bagwrite
from webbrowser import open as explorer_view
from os.path import join as pathj
from bpy.props import StringProperty,BoolProperty

# Path to Wreckfest install when not using Modding Toolbox
wreckfest_install = r"C:\Program Files (x86)\Steam\SteamApps\common\Wreckfest"


class WF_MODGEN_MT_menu(bpy.types.Menu):
    bl_idname = "WF_MODGEN_MT_menu"
    bl_label = "Create Wreckfest Mod"
    
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2
        #layout.operator("wf_modgen.create", text='Derby', icon='MESH_CAPSULE').template = 'Derby'

        example_files = pathj(os.path.dirname(os.path.realpath(__file__)),'example_files') # Example_Files folder

        # Create dropdown list of examples
        for (dirpath, dirnames, filenames) in os.walk(example_files):
            break
        for folder in dirnames:
            name = folder[5:]
            if folder[2]=='t': #Track
                icons = {'01t__Derby-Simple':'MESH_CAPSULE','02t_Race':'IPO_BACK'}
                if folder in icons:
                    layout.operator("wf_modgen.create", text=name, icon=icons[folder]).template = folder
                else:
                    layout.operator("wf_modgen.create", text=name).template = folder
            #else:
            #    layout.operator("wf_modgen.create", text=name).template = folder

        #layout.separator()
        #layout.label(text="Special:")


class WF_MODGEN_OT_create(bpy.types.Operator):
    """Create mod to: Wreckfest\\mods\\.."""
    bl_idname = "wf_modgen.create"
    bl_label = ""

    template : StringProperty(name="Template") # Input coming from menu

    def trackname_change(self,context):
        """Autofill based on track name field"""
        if(len(self.trackname)>0):
            self.title=self.trackname
            if 'derby' in self.template.lower(): self.eventtitle=self.trackname+' Derby'
            elif 'race' in self.template.lower(): self.eventtitle=self.trackname+' Race'
            else: self.eventtitle='Main Event'
            foldern = self.trackname.lower().replace(' ','_').replace('ä','a').replace('ö','o')
            foldern = re.sub('[^a-z0-9_]+', '', foldern)
            self.foldername = foldern
            self.groupname = foldern
            self.eventid = foldern+'_'+self.template[5:].lower()

    def view_update(self,context):
        """Update variables that control view"""
        # Paths
        mod_folder = pathj(self.wf_install,'mods',self.foldername)
        event_folder = pathj(mod_folder,'data','property','event', self.groupname)
        event_file = pathj(event_folder,self.eventid+'.evse')
        envi_file = pathj(event_folder,self.groupname+'.envi')
        # Update between data/track and data/art/levels
        if self.use_levelsf: self.scne_relpath = pathj('data', 'art', 'levels', self.groupname)
        else: self.scne_relpath = pathj('data', 'track', self.groupname)
        if self.use_eventf: self.scne_relpath = pathj(self.scne_relpath, self.eventid)
        self.scne_relpath = pathj(self.scne_relpath, self.eventid+'.scne')

        # Check if files exist on disk, Update view and trigger errors etc.
        self.mod_exists = os.path.exists(mod_folder) and self.foldername!=''
        self.envi_exists = os.path.exists(envi_file)
        self.event_exists = os.path.exists(event_file)
        self.scne_exists = os.path.exists(pathj(mod_folder,self.scne_relpath))

    # Variables to control view changes
    mod_exists : BoolProperty()
    envi_exists : BoolProperty()
    event_exists : BoolProperty()
    scne_exists : BoolProperty()

    # Path to wreckfest install from toolbox
    wf_install : StringProperty(name="test", default=wreckfest_install)
 
    #### UI Props ####
    trackname : StringProperty(name="Track Name", description="Title for autofill", default='', maxlen=0, update=trackname_change)
    # Folder
    foldername : StringProperty(name="Folder Name", description="Folder in Wreckfest\\mods\\\n\nNote: Wreckfest folder must be configured in Toolbox addon preferences.", maxlen=25,update=view_update)
    # Group
    groupname : StringProperty(name="Group Name", description="", maxlen=30, update=view_update)
    title : StringProperty(name="Title", description="Title seen in main menu")
    description : StringProperty(name="Description", description="Description seen in main menu")
    # Event
    eventid : StringProperty(name="Event Id", description="Unique Id to identify event.\n\nImportant:\n - Must be unique.\n - Other tracks sharing same Id may disappear", maxlen=30, update=view_update)
    eventtitle : StringProperty(name="Title", description="")
    gamemode : bpy.props.EnumProperty(
        items=(
            ('4', 'Derby','\nRequirements:\nNone\n\nMode known to load even with simple cube.', 'MESH_CAPSULE', 4), 
            ('1', 'Racing','\nRequirements:\n - Properly set Ai routes, startpoints and checkpoints.\n - Alt routes require .tcat file changes.\n\nNot filling requirements will crash game without error.', 'IPO_BACK', 1),
        ),
        name="Gamemode",
        description="Gamemode",
        default="4",
    )
    scne_relpath : StringProperty(name='Scene')
    use_levelsf : BoolProperty(name="Use levels folder", description="Use data\\art\\levels folder instead of data\\track\\", update=view_update)
    use_eventf : BoolProperty(name="Create event folder", description="Use data\\track\\group\\event\\ folder instead of data\\track\\group\\", update=view_update)
    name_on_server : StringProperty(name="test", description="Description seen in server", default='')


    def invoke(self, context, event):
        try:
            self.wf_install = bpy.context.preferences.addons['wreckfest_toolbox'].preferences.wf_path
        except:
            pass
        if "Race" in self.template: self.gamemode = "1" # Race in example name sets gamemode to Race
        self.view_update(context) # Fix layout if it was prefilled from history.
        return context.window_manager.invoke_props_dialog(self, width = 488) # Load as popup window
 
    def draw(self, context):
        """Draw popup window"""
        def layout_text(layout,text1,text2,factor=0.238):
            """Preformat for split text row"""
            row = layout.split(factor=factor)
            row.label(text=text1)
            row.label(text=text2)
        def layout_shortinput(layout,text,prop,alert=False,factor=0.245):
            """Preformat for split row with short input"""
            row = layout.split(factor=factor)
            row.alert=alert
            row.label(text=text)
            row.prop(self,prop, text="")
            row.label(text='') #Spacer
            row.label(text='')

        l = self.layout

        # Titlebar
        row=l.row()
        row=row.split(factor=0.65)
        box = row.box()
        box.label(text=" Wreckfest Mod Generator ")
        box = row.box()
        box.label(text='Template:  '+self.template[5:])
        l.separator(factor=3)

        # Track Name
        l.prop(self, "trackname")
        l.separator(factor=3)

        # Folder box
        box=l.box()
        if not self.mod_exists: 
            layout_text(box,'Folder:',pathj('mods',self.foldername))
        else:
            layout_text(box,'Existing Folder:',pathj('mods',self.foldername))
        layout_shortinput(box,'','foldername', alert=len(self.foldername)==0)
        box.separator(factor=3)
        l.separator(factor=0.5)

        # Group box (envi)
        box=l.box()
        envi_file = pathj('event', self.groupname, self.groupname+'.envi')
        if not self.envi_exists:
            layout_text(box,'Group:',envi_file)
            layout_shortinput(box,'','groupname',alert=len(self.groupname)==0)
            box.prop(self, "title")
            box.prop(self, "description")
        else:
            layout_text(box,'Existing Group:',envi_file)
            layout_shortinput(box,'','groupname',alert=len(self.groupname)==0)
        box.separator(factor=3)
        l.separator(factor=0.5)

        # Event box (evse)
        box = l.box()
        evse_file = pathj('event', self.groupname, self.eventid+'.evse')
        if not self.event_exists:
            layout_text(box,'Event:',evse_file)
        else:
            layout_text(box,'Existing Event: ',evse_file)
        layout_shortinput(box,'','eventid',alert=(self.event_exists or len(self.eventid)==0))
        box.prop(self, "eventtitle")
        scne = self.scne_relpath
        layout_shortinput(box,'Gamemode','gamemode')
        layout_text(box,'Scene',scne)
        layout_shortinput(box,'Use levels folder','use_levelsf')
        layout_shortinput(box,'Make event folder','use_eventf')

        # Footer
        l.separator(factor=3)
        layout_text(l,'Name on server:',self.eventid+' ('+self.title.upper()+' - '+self.eventtitle.upper()+')')
        l.separator(factor=3)

        # Warning
        if bpy.app.version < (3,1) and 'Derby' in self.template:
            row=l.row()
            row.alert=True
            row.label(text='Warning: Template requires Blender version 3.1 or greater')
            l.separator(factor=3)

    def execute(self, context):
        """Generate Mod"""
        mods_folder = pathj(self.wf_install,'mods')
        mod_folder = pathj(mods_folder,self.foldername)
        event_folder = pathj(mods_folder,self.foldername,'data','property','event',self.groupname)
        evse_file = pathj(event_folder, self.eventid+'.evse')
        scne_file = pathj(mod_folder, self.scne_relpath)
        addon_folder = os.path.dirname(os.path.realpath(__file__))
        example_files = pathj(addon_folder,'example_files',self.template) # mode = mod folder
        example_shared_files = pathj(addon_folder,'example_shared','t') # t = track folder

        if self.title=='': self.title = self.groupname
        if self.eventtitle=='': self.eventtitle = self.groupname

        if self.foldername=='' or self.groupname=='' or self.groupname=='':
            self.report({'ERROR'}, "You left fields empty!")
        elif not os.path.exists(mods_folder):
            self.report({'ERROR'}, "Mods folder not found: "+mods_folder+"\nSet path to Wreckfest in Wreckfest toolbox addon properties")
        elif os.path.exists(evse_file):
            self.report({'ERROR'}, 'EVSE already exists at: '+evse_file)
        elif os.path.exists(scne_file):
            self.report({'ERROR'}, 'SCNE already exists at: '+scne_file)
        else:
            print("\nStarting Wreckfest Mod Generation")

            if not self.envi_exists:
                # Make envi event group
                os.makedirs(event_folder)
                file = bagwrite.BagWrite()
                file.envi_file(title=self.title, desc=self.description, location='')
                file.save(pathj(event_folder,self.groupname+'.envi'))

                # Make modinfo
                modinfo = pathj(mod_folder,'modinfo.modi')
                if not os.path.exists(modinfo):
                    file = bagwrite.BagWrite()
                    file.modi_file(name=self.title, desc=self.description, tagbits=8)
                    file.save(modinfo)

                # Make weather list
                folder = pathj(mod_folder,'data','property','weather', self.groupname)
                weatherlist = pathj(folder, self.groupname+'.weli')
                if not os.path.exists(weatherlist):
                    os.makedirs(folder)
                    file = bagwrite.BagWrite()
                    file.weli_file(['data/property/weather/'+self.groupname+'/midday1.weat',])
                    file.save(weatherlist)

            # Make evse event
            file = bagwrite.BagWrite()
            file.evse_file(title=self.eventtitle,
                            desc='',
                            gamemode=int(self.gamemode),
                            scne=self.scne_relpath.replace('\\','/'),
                            weli='data/property/weather/'+self.groupname+'/'+self.groupname+'.weli')
            file.save(evse_file)

            # Make scne file
            # print("\nScne File:",scne_file)
            scne_folder = os.path.dirname(scne_file)
            # if not os.path.exists(scne_folder): os.makedirs(scne_folder)
            # shutil.copyfile(pathj(example_files,'Derby','simpletrack.scne'), scne_file)
            # shutil.copyfile(pathj(example_files,'Derby','simpletrack.blend'), pathj(scne_folder,self.eventid+'.blend'))
            # print(example_files)
            #explorer_view(scne_folder+'\\')


            def copy_folder(path_in,path_out,):
                """Copy Wreckfest mod folder and rename in fly"""
                print("Copying from: ",path_in)
                for root, dirnames, filenames in os.walk(path_in):
                    for filename in filenames:
                        file_in = os.path.join(root, filename)
                        len_remove = len(path_in)+1
                        in_rel_path = file_in[len_remove:] #subpath without path_in
                        # Fix files to use group/event/ folder
                        if self.use_eventf:
                            in_rel_path = in_rel_path.replace('data/track/#group/', 'data/track/#group/#track/')
                            in_rel_path = in_rel_path.replace('data\\track\\#group\\', 'data\\track\\#group\\#track\\')
                        # Fix files to use data/art/levels
                        if self.use_levelsf:
                            in_rel_path = in_rel_path.replace('data/track/','data/art/levels/')
                            in_rel_path = in_rel_path.replace('data\\track\\','data\\art\\levels\\')
                        # Replace tags in filenames
                        in_rel_path = in_rel_path.replace('#group',self.groupname)
                        in_rel_path = in_rel_path.replace('#track',self.eventid)
                        # Copy if no existing and make folders
                        print("Copying: ", in_rel_path)
                        file_out = pathj(path_out,in_rel_path)
                        out_folder = os.path.dirname(file_out)
                        if not os.path.exists(out_folder):
                            os.makedirs(out_folder)
                        if not os.path.exists(file_out): 
                            shutil.copyfile(file_in, file_out)
                        else:
                            print("File exists, skipping: ",file_out)
    
            copy_folder( example_shared_files, mod_folder)
            copy_folder( example_files, mod_folder)

            if os.path.exists(scne_folder):
                explorer_view(scne_folder)
                blend_file = scne_file[:-5]+'.blend'
                if os.path.exists(blend_file):
                    bpy.ops.wm.open_mainfile(filepath=blend_file)
            else:
                explorer_view(mod_folder)

            self.report({'INFO'}, "Mod generated at: "+mod_folder)

        return {'FINISHED'}
        



def draw_wf_modgen_menu(self, context):
    layout = self.layout
    icon = 'FOLDER_REDIRECT' 
    if bpy.app.version<(2,83): icon = 'NEWFOLDER' 
    layout.menu(WF_MODGEN_MT_menu.bl_idname, icon=icon)



def register():
    bpy.utils.register_class(WF_MODGEN_MT_menu)
    bpy.utils.register_class(WF_MODGEN_OT_create)    
    # Add to File > New menu
    bpy.types.TOPBAR_MT_file_new.append(draw_wf_modgen_menu)

def unregister():
    bpy.utils.unregister_class(WF_MODGEN_MT_menu)
    bpy.utils.unregister_class(WF_MODGEN_OT_create)
    # Remove from File > New menu
    bpy.types.TOPBAR_MT_file_new.remove(draw_wf_modgen_menu)

if __name__ == "__main__":
    register()

    # The menu can also be called from scripts
    bpy.ops.wm.call_menu(name=WF_MODGEN_MT_menu.bl_idname)
