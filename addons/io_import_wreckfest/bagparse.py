""" Wreckfest Bagfile Reader

Bagfile Reader handles reading of most common data types from binary data.

Example usage:
    import bagparse
    file = open("uncompressed.raw.scne","rb")
    parse = bagparse.BagParse(file.read())
    parse.skipToHeader('ssce')
    version = parse.i()
    number = parse.i()
    print('Found',number,'subscenes')

License:
    This program is licensed under Creative Commons CC0
    https://creativecommons.org/publicdomain/zero/1.0/
"""

import struct

def popup(title):
    raise ValueError('File failed to import. Details:\n'+title)

class BagParse:
    """Read uncompressed Wreckfest Bagfiles"""
    def __init__(self,bytes = 0):
        """Initialize class with binary data"""
        self.bytes = bytes #scne data
        self.p = 0 #pointer
        self.endian = '<' #Little Endianess < = little

    def readBytes(self,length=4):
        """Read raw bytes by length"""
        data = self.bytes[self.p:self.p+length]
        self.p += length
        return data    
        
    def skipTo(self,skipto):
        """Skips to next place that match search keyword"""
        position = self.bytes.find(skipto, self.p)
        success = (position != -1)
        if success:
            self.p = position + len(skipto) 
        return success

    def skipToHeader(self,header):
        """
            Skips to next four character Wreckfest header
            Skips to next occurence of 4 character text that is followed by version < 20
        """
        if self.endian=='<': header = header[::-1] #reverse
        header_r = header.encode()  #encode to bytes
        while self.skipTo(header_r):
            version = self.i(4)
            if version>=0 and version<70: #valid version number follows header
                self.p -= 4 #undo pointer move
                return #Proper header found
        popup("Import failed, header not found: "+str(header))
    
    def skip(self,length=4):
        """Move pointer"""
        self.p += length

    def tell(self):
        """Get pointer position"""
        return self.p
  
    def read(self, param, endian=''): 
        """Read using struct.unpack parameters"""
        data = self.readBytes(struct.calcsize(param))
        if endian == '': endian = self.endian
        return struct.unpack(endian+param, data)

    def i(self,length=4):
        """Read int"""
        data = self.readBytes(length)
        bo = 'little' if self.endian=='<' else 'big'
        return int.from_bytes(data, byteorder=bo, signed=True)
        
    def f(self,length=4):
        """Read float"""
        data = self.readBytes(length)
        return struct.unpack(self.endian+'f', data)[0]

    def text(self,length=0):
        """Read text with manually set length"""
        return self.readBytes(length).decode("utf-8",'backslashreplace')
    
    def wftext(self): 
        """Read Wreckfest text field (int, text)"""
        length = self.i()
        return self.text(length)   

    def wfdata(self): 
        """Read Wreckfest binary data field (int, data)"""
        length = self.i()
        return self.readBytes(length)

    def checkHeader(self,headerCheck):
        """Read Wreckfest 4 character header and verify it match headerCheck"""
        header = self.text(4)
        if self.endian=='<': header = header[::-1] #reverse header  
        if header==headerCheck:
            return True
        if header=='\x00\x00\x00\x00' : 
            self.skip(4) #empty header always followed by 4 bytes
            return False    
        longname = {'scne':'Subscene', 'pmsh':'Model', 'aisc':'Airoute'}.get(headerCheck, headerCheck) # default = headerCheck
        popup(longname+' import failed.')
        return False
    
    def matrix(self, length=64):
        """Read Wreckfest transform matrix, Swap Y and Z for 3D software use"""
        data = self.readBytes(length)
        v = struct.unpack(self.endian+'16f', data)
        #matrix
        x = (v[0], v[1], v[2], v[3])
        y = (v[4], v[5], v[6], v[7])
        z = (v[8], v[9], v[10], v[11])
        w = (v[12],v[13], v[14], v[15])
        #swapping Y and Z (third and second row, and third and second column    
        mx = (x[0],x[2],x[1],x[3]), (z[0],z[2],z[1],z[3]), (y[0],y[2],y[1],y[3]), (w[0],w[2],w[1],w[3])    
        return mx

    def aabb(self):
        """Read Wreckfest bounding box, flip y&z"""
        return {
            "cx": self.f(),
            "cz": self.f(),
            "cy": self.f(),
            "ex": self.f(),
            "ez": self.f(),
            "ey": self.f(),
        }