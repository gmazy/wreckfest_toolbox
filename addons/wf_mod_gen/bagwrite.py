# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons CC0
# https://creativecommons.org/publicdomain/zero/1.0/
#
# ##### END LICENSE BLOCK #####


import struct
import random

class BagWrite:
    def __init__(self):
        """ Initialize as uncompressed file """
        self.data = b''
        self.i(1) # 1 = uncompressed, 4 = lz4

    def i(self,int): 
        """ Add int """
        self.data += struct.pack('<i', int)

    def text(self,text):
        self.data += str.encode(text)

    def wftext(self,text): 
        """ Add text """
        self.i(len(text))
        self.text(text)

    def header(self,header,v=0,num=0):
        """ Add Header """
        self.data += str.encode(header)
        self.i(v)
        if num!='':
            self.i(num)

    def tran(self,trantype,textvalue):
        """ Add tran (translation?) section """
        def random_number(seed):
            random.seed(seed)
            r = str(random.random())
            return r[-10:] # 10 last numbers

        self.header('nart',v=2,num=1)
        if textvalue=='': # Empty section
            self.i(0)
            self.i(0)
        else: # Normal section: Type + 10 numbers + length
            self.wftext( trantype + random_number(textvalue) + '_' + str(len(textvalue)) )
            self.wftext( textvalue )

    def section(self,name,value):
            if(value==''): # Empty section
                self.i(0)
                self.i(0)
            else:
                self.text(name)
                self.wftext(value)

    def save(self,filename):
        """ Save to file """
        with open(filename, 'wb') as f:
            f.write(self.data)
            print("Create:",filename)


    def envi_file(self,title,desc='',location=''):
        """ Add envi file content """
        self.header('ivne',v=3,num=2) # Version:3, Number of: 2
        self.tran('ENVIRONMENT_TITLE_',title)
        self.tran('ENVIRONMENT_DESCRIPTION_',desc)
        self.tran('ENVIRONMENT_LOCATION_',location)
        self.header('rsve',v=0,num=0)
        self.i(0)
        self.i(0)
        self.i(0)

    def evse_file(self,title,desc='',state=2, gamemode=4,scne='',weli='data/property/weather/example/example.weli',sfxm=''):
        """ Add evse file content """
        self.header('esve',v=17,num='')
        self.i(state) # State: 1=Developer, 2=Final, 3=Disabled, 4=Mod
        self.i(0) # Tournament Only: 0=Off, 1=On
        self.tran('EVENT_TITLE_',title)
        self.tran('EVENT_DESCRIPTION_',desc)
        self.i(gamemode) # Gamemode: 0=None, 1=Racing, 2=None, 4=Derby
        self.wftext(scne)
        self.section('ilew',weli) # Weather List
        self.i(0) # PS4 Leaderboard Base Index
        self.section('mxfs',sfxm) # Sfxm Mapping
        for i in range(15): self.i(0)
        self.data +=b'\xff\xff\xff\xff'
        self.data +=b'\xff\xff\xff\xff'
        for i in range(10): self.i(0)
        self.data += b'\x00\x00'

    def modi_file(self,name='',preview='preview.jpg',desc='',cnote='',visibility=2,tagbits=0):
        """ Add modinfo file content """
        self.header('idom',v=0,num='')
        self.wftext(name)
        self.wftext(preview)
        self.wftext(desc)
        self.wftext(cnote)
        self.i(visibility) # 0=public, 1=friends, 2=private
        self.i(tagbits) # Tags #1=car, 2=skin, 8=track, 16=object
        self.i(0) # Published id
        self.i(0)

    def weli_file(self,pathlist=[]):
        """ Add weather list file content """
        self.header('ilew',v=0,num='')
        self.header('lbew',v=0,num=len(pathlist))
        for filepath in pathlist:
            self.section('taew',filepath)

    def prfb_file(self,pathlist=[]):
        """ Add prefab list file content """
        self.header('bfrp',v=0,num='')
        self.header('tirp',v=0,num=len(pathlist))
        for filepath in pathlist:
            self.section('nuoj',filepath)